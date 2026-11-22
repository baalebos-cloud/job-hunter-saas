"""Object storage, async refiner jobs, read routing, migrations and N+1 checks."""
import io
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.config import settings
from backend.app.database import Base, get_db
from backend.app.main import app, reset_rate_limits
from backend.app.models.application import Application
from backend.app.models.job import Job
from backend.app.models.resume import Resume
from backend.app.models.subscription import Subscription
from backend.app.models.user import User
from backend.app.services import resume_storage
from backend.app.services.auth_service import create_access_token
from backend.app.utils.pdf_generator import export_resume

ROOT = Path(__file__).resolve().parents[2]


class FakeS3:
    def __init__(self):
        self.objects, self.calls = {}, []

    def put_object(self, **kw):
        self.calls.append(('put', kw)); self.objects[kw['Key']] = kw['Body']

    def get_object(self, Bucket, Key):
        return {'Body': io.BytesIO(self.objects[Key])}

    def delete_object(self, Bucket, Key):
        self.calls.append(('delete', Key)); self.objects.pop(Key, None)

    def generate_presigned_url(self, op, ExpiresIn, Params):
        return f"https://s3.example/{Params['Key']}?X-Amz-Expires={ExpiresIn}"


@pytest.fixture
def s3(monkeypatch):
    fake = FakeS3()
    monkeypatch.setenv('RESUME_S3_BUCKET', 'private-resumes')
    monkeypatch.setenv('RESUME_S3_KMS_KEY_ID', 'arn:aws:kms:us-east-1:111122223333:key/test')
    monkeypatch.setattr(resume_storage, 'client', lambda: fake)
    return fake


@pytest.fixture
def db(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(User(email='a@example.com', full_name='A', hashed_password='x', is_verified=True, country='Nigeria'))
    session.commit()
    monkeypatch.setattr('backend.app.database.SessionLocal', Session)
    app.dependency_overrides[get_db] = lambda: session
    reset_rate_limits()
    yield session
    from backend.app.services import audit
    audit.flush()          # drain queued request records before the shared connection closes
    app.dependency_overrides.clear(); session.close(); engine.dispose()


@pytest.fixture
def client(db):
    return TestClient(app)


AUTH = {'Authorization': 'Bearer ' + create_access_token({'sub': 'a@example.com'})}
BASE = {'name': 'Ada Obi', 'title': '', 'contact': 'ada@example.com', 'summary': 'Python engineer.',
        'experience': [{'role': 'Engineer', 'company': 'Acme', 'dates': '2021', 'bullets': ['Built Python tools.'], 'environment': ''}],
        'projects': [], 'skills': {'Skills': ['Python']}, 'certifications': [],
        'education': [{'degree': 'BSc', 'institution': 'Unilag', 'year': '2019'}], 'additional_information': ''}


@pytest.fixture
def pipeline(monkeypatch):
    import backend.app.utils.ats_engine as engine
    monkeypatch.setattr(engine, 'extract_resume_data', lambda text: json.loads(json.dumps(BASE)))
    monkeypatch.setattr(engine, 'extract_requirements', lambda jd: [{'phrase': 'Python', 'priority': 'required'},
                                                                    {'phrase': 'Terraform', 'priority': 'required'}])
    monkeypatch.setattr(engine, 'rewrite_resume_for_job', lambda **kw: {
        'optimized_summary': BASE['summary'], 'optimized_experience': [{k: v for k, v in BASE['experience'][0].items() if k != 'environment'}],
        'optimized_skills': {'Skills': ['Python']}, 'confirmation_questions': [], 'suggestions_applied': []})


def upload(client):
    return client.post('/api/v1/resume/upload', headers=AUTH,
                       files={'file': ('cv.pdf', export_resume(BASE).pdf, 'application/pdf')},
                       data={'job_title': 'Engineer', 'job_description': 'Python and Terraform required for this platform role.'})


# ── Object storage ───────────────────────────────────────────────────────────

def test_pdfs_go_to_kms_encrypted_s3_not_the_database(client, db, s3, pipeline):
    res = upload(client)
    assert res.status_code == 200, res.text
    record = db.query(Resume).one()
    assert record.content is None and record.storage_key.startswith(f'resumes/{record.owner_id}/')
    put = s3.calls[0][1]
    assert put['ServerSideEncryption'] == 'aws:kms' and put['SSEKMSKeyId'].endswith(':key/test')
    assert put['Bucket'] == 'private-resumes' and put['ContentType'] == 'application/pdf'
    task_id = res.json()['task_id']
    pdf = client.get(f'/api/v1/resume/download/{task_id}', headers=AUTH).content
    assert pdf == s3.objects[record.storage_key] and len(pdf) == record.size_bytes
    url = client.get(f'/api/v1/resume/url/{task_id}', headers=AUTH).json()
    assert url['url'].startswith('https://s3.example/resumes/') and url['expires_in'] == 300


def test_integrity_check_rejects_tampered_objects(client, db, s3, pipeline):
    task_id = upload(client).json()['task_id']
    record = db.query(Resume).one()
    s3.objects[record.storage_key] = b'%PDF-1.4 tampered'
    assert client.get(f'/api/v1/resume/download/{task_id}', headers=AUTH).status_code == 500


def test_regenerate_replaces_object_and_failed_commit_cleans_up(client, db, s3, pipeline, monkeypatch):
    task_id = upload(client).json()['task_id']
    old_key = db.query(Resume).one().storage_key
    res = client.post(f'/api/v1/resume/regenerate/{task_id}', headers=AUTH, json={'confirmed_keywords': ['Terraform']})
    assert res.status_code == 200
    new_key = db.query(Resume).one().storage_key
    assert new_key != old_key and old_key not in s3.objects and new_key in s3.objects
    real_commit = db.commit
    monkeypatch.setattr(db, 'commit', lambda: (_ for _ in ()).throw(RuntimeError('db down')))
    before = set(s3.objects)
    res = client.post(f'/api/v1/resume/regenerate/{task_id}', headers=AUTH, json={'confirmed_keywords': []})
    monkeypatch.setattr(db, 'commit', real_commit)
    assert res.status_code == 500 and set(s3.objects) == before  # orphan object removed


def test_database_fallback_without_bucket(client, db, pipeline, monkeypatch):
    monkeypatch.delenv('RESUME_S3_BUCKET', raising=False)
    task_id = upload(client).json()['task_id']
    record = db.query(Resume).one()
    assert record.content.startswith(b'%PDF') and record.storage_key is None and record.sha256
    assert client.get(f'/api/v1/resume/url/{task_id}', headers=AUTH).json()['url'] is None


# ── Async refiner jobs (202 + polling) ───────────────────────────────────────

@pytest.fixture
def async_mode(monkeypatch):
    monkeypatch.setattr(settings, 'RESUME_PROCESSING_MODE', 'async')
    queued = []
    from backend.app.tasks import resume_tasks
    monkeypatch.setattr(resume_tasks.process_resume_upload, 'apply_async', lambda args, task_id, **kw: queued.append(args))
    return queued


def test_async_upload_returns_202_then_worker_completes(client, db, pipeline, async_mode):
    res = upload(client)
    assert res.status_code == 202 and res.json()['status'] == 'processing'
    task_id = res.json()['task_id']
    assert res.headers['location'] == f'/api/v1/resume/status/{task_id}'
    assert client.get(f'/api/v1/resume/status/{task_id}', headers=AUTH).json() == {'task_id': task_id, 'status': 'processing'}
    assert client.get(f'/api/v1/resume/download/{task_id}', headers=AUTH).status_code == 409
    assert (db.query(Subscription).first().scans_this_month if db.query(Subscription).first() else 0) == 0
    from backend.app.tasks.resume_tasks import process_resume_upload
    assert process_resume_upload.run(*async_mode[0])['status'] == 'completed'
    db.expire_all()
    status = client.get(f'/api/v1/resume/status/{task_id}', headers=AUTH).json()
    assert status['status'] == 'completed' and status['result']['document']['pages'] == 1
    assert db.query(Subscription).one().scans_this_month == 1
    assert client.get(f'/api/v1/resume/download/{task_id}', headers=AUTH).content.startswith(b'%PDF')


def test_async_failure_is_reported_and_not_charged(client, db, pipeline, async_mode, monkeypatch):
    task_id = upload(client).json()['task_id']
    monkeypatch.setattr('backend.app.utils.ats_engine.extract_resume_data', lambda text: (_ for _ in ()).throw(RuntimeError('provider down')))
    from backend.app.tasks.resume_tasks import process_resume_upload
    assert process_resume_upload.run(*async_mode[0])['status'] == 'failed'
    db.expire_all()
    status = client.get(f'/api/v1/resume/status/{task_id}', headers=AUTH).json()
    assert status['status'] == 'failed' and 'Reference' in status['error'] and 'provider down' not in status['error']
    sub = db.query(Subscription).first()
    assert sub is None or sub.scans_this_month == 0


def test_stuck_jobs_expire_and_in_flight_jobs_count_against_quota(client, db, pipeline, async_mode):
    from backend.app.models.subscription import PLANS
    first = upload(client).json()['task_id']
    for _ in range(PLANS['free']['scans_per_month'] - 1):
        assert upload(client).status_code == 202
    assert upload(client).status_code == 403  # every free scan is in flight
    record = db.query(Resume).filter(Resume.filename == f'optimized_{first}.pdf').one()
    record.updated_at = datetime.utcnow() - timedelta(minutes=settings.RESUME_JOB_TIMEOUT_MINUTES + 1)
    db.commit()
    status = client.get(f'/api/v1/resume/status/{first}', headers=AUTH).json()
    assert status['status'] == 'failed' and 'took too long' in status['error']


def test_queue_outage_fails_fast(client, db, pipeline, monkeypatch):
    monkeypatch.setattr(settings, 'RESUME_PROCESSING_MODE', 'async')
    from backend.app.tasks import resume_tasks
    monkeypatch.setattr(resume_tasks.process_resume_upload, 'apply_async',
                        lambda **kw: (_ for _ in ()).throw(ConnectionError('redis down')))
    res = upload(client)
    assert res.status_code == 503 and 'queue is unavailable' in res.json()['detail']
    assert db.query(Resume).one().status == 'failed'


# ── Read replica routing ─────────────────────────────────────────────────────

def test_read_dependency_uses_replica_when_configured(monkeypatch):
    import backend.app.database as database
    sentinel = object()
    class ReplicaSession:
        closed = False
        def close(self): ReplicaSession.closed = True
    monkeypatch.setattr(database, 'ReadSessionLocal', ReplicaSession)
    gen = database.get_read_db(primary=sentinel)
    session = next(gen)
    assert isinstance(session, ReplicaSession)
    with pytest.raises(StopIteration):
        next(gen)
    assert ReplicaSession.closed
    monkeypatch.setattr(database, 'ReadSessionLocal', None)
    assert next(database.get_read_db(primary=sentinel)) is sentinel


# ── N+1 elimination ──────────────────────────────────────────────────────────

def test_admin_listings_use_constant_query_count(client, db):
    db.query(User).filter_by(email='a@example.com').update({'role': 'super_admin'})
    for i in range(6):
        user = User(email=f'u{i}@example.com', hashed_password='x', is_verified=True)
        job = Job(title=f'Job {i}', company='Co', url=f'https://example.com/{i}')
        db.add_all([user, job]); db.flush()
        db.add_all([Application(user_id=user.id, job_id=job.id), Application(user_id=user.id, job_id=job.id)])
    db.commit()
    from backend.app.dependencies.roles import ensure_rbac_seed
    ensure_rbac_seed(db)  # one-time policy seed is not part of the listing cost
    statements = []
    listener = lambda *args: statements.append(args[2])
    event.listen(db.get_bind(), 'before_cursor_execute', listener)
    try:
        users = client.get('/api/v1/admin/users', headers=AUTH)
        users_queries = len(statements); statements.clear()
        apps = client.get('/api/v1/admin/applications', headers=AUTH)
        app_queries = len(statements)
    finally:
        event.remove(db.get_bind(), 'before_cursor_execute', listener)
    assert users.status_code == 200 and sum(u['applications'] for u in users.json()) == 12
    assert apps.status_code == 200 and len(apps.json()) == 12 and all(a['user_email'] for a in apps.json())
    # auth + rbac lookups + one listing query; independent of row count
    assert users_queries <= 6 and app_queries <= 6, (users_queries, app_queries)


# ── Migrations ───────────────────────────────────────────────────────────────

def _migrate(url):
    env = {**os.environ, 'DATABASE_URL': url, 'SECRET_KEY': 'x', 'ENVIRONMENT': 'test'}
    return subprocess.run([sys.executable, '-m', 'backend.scripts.migrate'], cwd=ROOT, env=env, capture_output=True, text=True)


def test_migration_bootstrap_on_fresh_and_legacy_databases(tmp_path):
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    head = ScriptDirectory.from_config(Config(str(ROOT / 'backend/alembic.ini'))).get_current_head()
    fresh = f'sqlite:///{tmp_path}/fresh.db'
    result = _migrate(fresh)
    assert result.returncode == 0, result.stderr[-2000:]
    engine = create_engine(fresh)
    with engine.connect() as conn:
        assert conn.execute(text('SELECT version_num FROM alembic_version')).scalar() == head
    indexes = {i['name'] for i in inspect(engine).get_indexes('applications')}
    assert {'ix_applications_user_created', 'ix_applications_job_status'} <= indexes
    assert _migrate(fresh).returncode == 0  # idempotent


def test_startup_performs_no_ddl():
    source = (ROOT / 'backend/app/main.py').read_text()
    assert 'ALTER TABLE' not in source and 'create_all' not in source


def test_blob_backfill_moves_verifies_and_is_resumable(db, s3):
    import hashlib
    from backend.scripts import migrate_resume_blobs
    for i in range(3):
        db.add(Resume(owner_id=1, filename=f'optimized_{i}.pdf', content=b'%PDF-' + bytes([i]) * 50))
    db.commit()
    assert migrate_resume_blobs.main(['--batch', '2']) == 0
    db.expire_all()
    rows = db.query(Resume).order_by(Resume.id).all()
    assert all(r.content is None and r.storage_key and r.sha256 for r in rows)
    assert all(hashlib.sha256(s3.objects[r.storage_key]).hexdigest() == r.sha256 for r in rows)
    assert migrate_resume_blobs.main([]) == 0  # nothing left; safe to re-run
