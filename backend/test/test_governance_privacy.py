"""Audit trail, GDPR export/erasure, metrics, governance API and concurrency."""
import io
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core import kv_store
from backend.app.core.config import settings
from backend.app.database import Base, get_db
from backend.app.main import app, reset_rate_limits
from backend.app.models.application import Application
from backend.app.models.audit import AuditLog, ErasureTombstone
from backend.app.models.job import Job
from backend.app.models.referral import Referral
from backend.app.models.resume import Resume
from backend.app.models.security import RefreshToken
from backend.app.models.subscription import Subscription
from backend.app.models.user import Education, OutreachMessage, User
from backend.app.services import audit, resume_storage
from backend.app.services.auth_service import create_access_token, hash_password

EMAIL = 'ada.obi@example.com'


@pytest.fixture
def db(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add_all([
        User(email=EMAIL, full_name='Ada Obi', hashed_password=hash_password('pw-12345678'), is_verified=True, country='Nigeria',
             verification_token='a' * 64),
        User(email='officer@example.com', full_name='Officer', hashed_password='x', is_verified=True, role='compliance_officer'),
        User(email='viewer@example.com', full_name='Viewer', hashed_password='x', is_verified=True, role='viewer'),
        User(email='auditor@example.com', full_name='Auditor', hashed_password='x', is_verified=True, role='security_auditor'),
        User(email='other@example.com', full_name='Other', hashed_password='x', is_verified=True),
    ])
    session.commit()
    monkeypatch.setattr('backend.app.database.SessionLocal', Session)
    app.dependency_overrides[get_db] = lambda: session
    reset_rate_limits()
    yield session
    audit.flush()
    app.dependency_overrides.clear(); session.close(); engine.dispose()


@pytest.fixture
def client(db):
    return TestClient(app, base_url='https://testserver')


def auth(email=EMAIL, tv=0):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': email, 'tv': tv})}


def uid(db, email):
    return db.query(User).filter_by(email=email).one().id


# ── Audit trail ──────────────────────────────────────────────────────────────

def test_every_request_is_audited_without_raw_pii(client, db, caplog):
    caplog.set_level(logging.INFO, logger='audit')
    client.get('/api/v1/auth/me?email=leak@example.com', headers={**auth(), 'X-Forwarded-For': '198.51.100.77'})
    client.get('/api/v1/rbac/matrix', headers=auth())  # 403
    client.get('/api/v1/auth/me')                        # 401
    audit.flush()
    rows = db.query(AuditLog).filter(AuditLog.kind == 'request').order_by(AuditLog.id).all()
    assert [r.status for r in rows] == [200, 403, 401]
    first = rows[0]
    assert first.route == '/api/v1/auth/me' and first.method == 'GET' and len(first.trace_id) == 32
    assert first.actor_display == 'a***@e***.com' and first.actor_hash and EMAIL not in json.dumps(first.details or {})
    assert first.ip_masked in ('testclient', 'unknown') or first.ip_masked.endswith('/24')
    assert [r.outcome for r in rows] == ['success', 'denied', 'denied']
    assert EMAIL not in caplog.text and 'leak@example.com' not in caplog.text and '198.51.100.77' not in caplog.text


def test_trace_id_propagates_from_traceparent(client):
    trace = '4bf92f3577b34da6a3ce929d0e0e4736'
    res = client.get('/api/v1/auth/me', headers={**auth(), 'traceparent': f'00-{trace}-00f067aa0ba902b7-01'})
    assert res.headers['x-trace-id'] == trace


def test_record_event_redacts_emails():
    entry = {}
    original = audit.emit
    try:
        audit.emit = lambda e, persist=True: entry.update(e)
        audit.record_event('test.event', details={'note': 'contact jane.doe@corp.com now'})
    finally:
        audit.emit = original
    assert 'jane.doe@corp.com' not in json.dumps(entry['details']) and 'j***@c***.com' in entry['details']['note']


# ── GDPR Art. 15 export ──────────────────────────────────────────────────────

def seed_footprint(db):
    user = db.query(User).filter_by(email=EMAIL).one()
    other = db.query(User).filter_by(email='other@example.com').one()
    job = Job(title='Platform', company='Acme', url='https://example.com/j', posted_by_hr=True, hr_user_id=user.id, user_id=user.id)
    other_job = Job(title='Data', company='Beta', url='https://example.com/k')
    db.add_all([job, other_job]); db.flush()
    resume = Resume(owner_id=user.id, filename='optimized_t1.pdf', content=None, storage_key=f'resumes/{user.id}/obj.pdf',
                    sha256='0' * 64, parsed_data=json.dumps({'name': 'Ada Obi'}), analysis_data={'task_id': 't1'})
    db.add(resume); db.flush()
    application = Application(user_id=user.id, job_id=other_job.id, resume_id=resume.id)
    others_application = Application(user_id=other.id, job_id=job.id)
    db.add_all([application, others_application]); db.flush()
    db.add_all([
        OutreachMessage(user_id=user.id, application_id=application.id, message='Hello'),
        Subscription(user_id=user.id, plan='free', status='active'),
        RefreshToken(user_id=user.id, token_hash='b' * 64, family_id='f', expires_at=datetime.utcnow() + timedelta(days=1)),
        Referral(referrer_id=user.id, referred_email='friend@example.com'),
        Referral(referrer_id=other.id, referred_email=EMAIL, referred_user_id=user.id),
        Education(user_id=user.id, degree='BSc', institution='Unilag'),
    ])
    db.commit()
    return user, job


def test_dsar_export_is_complete_and_excludes_secrets(client, db):
    seed_footprint(db)
    res = client.get('/api/v1/privacy/export', headers=auth())
    assert res.status_code == 200 and 'attachment' in res.headers['content-disposition']
    bundle = res.json()
    assert bundle['format'] == 'baalebos.dsar.v1' and bundle['profile']['email'] == EMAIL
    for secret in ('hashed_password', 'verification_token', 'reset_token', 'token_version'):
        assert secret not in bundle['profile']
    assert bundle['resumes'][0]['parsed_data'] == {'name': 'Ada Obi'} and 'content' not in bundle['resumes'][0]
    assert len(bundle['applications']) == 1 and len(bundle['referrals']) == 2 and bundle['profile_details']['education_entries']
    assert len(bundle['active_sessions']) == 1 and 'token_hash' not in json.dumps(bundle['active_sessions'])
    for _ in range(4):
        client.get('/api/v1/privacy/export', headers=auth())
    assert client.get('/api/v1/privacy/export', headers=auth()).status_code == 429


# ── GDPR Art. 17 erasure ─────────────────────────────────────────────────────

class FakeS3:
    def __init__(self, fail=False):
        self.deleted, self.fail = [], fail

    def delete_object(self, Bucket, Key):
        if self.fail:
            raise ConnectionError('s3 down')
        self.deleted.append(Key)


def test_account_erasure_is_transactional_and_complete(client, db, monkeypatch):
    s3 = FakeS3()
    monkeypatch.setattr(resume_storage, 'client', lambda: s3)
    monkeypatch.setenv('RESUME_S3_BUCKET', 'private-resumes')
    user, job = seed_footprint(db)
    user_id, key = user.id, f'resumes/{user.id}/obj.pdf'
    token = auth()
    res = client.delete('/api/v1/profile/me', headers=token)
    assert res.status_code == 200 and res.json()['objects_pending'] == 0
    db.expire_all()
    assert db.query(User).filter_by(email=EMAIL).first() is None
    for model, column in ((Resume, Resume.owner_id), (Application, Application.user_id), (OutreachMessage, OutreachMessage.user_id),
                          (Subscription, Subscription.user_id), (RefreshToken, RefreshToken.user_id), (Education, Education.user_id)):
        assert db.query(model).filter(column == user_id).count() == 0, model.__name__
    assert db.query(Application).count() == 1  # the other candidate's application survives
    detached = db.get(Job, job.id)
    assert detached.hr_user_id is None and detached.is_active is False
    assert db.query(Referral).filter(Referral.referred_email == EMAIL).count() == 0
    assert db.query(Referral).filter(Referral.referred_email == 'erased').count() == 1
    assert s3.deleted == [key]
    tombstone = db.query(ErasureTombstone).one()
    assert tombstone.completed_at and EMAIL not in json.dumps(tombstone.deleted_counts)
    assert client.get('/api/v1/auth/me', headers=token).status_code == 401
    audit.flush()
    event = db.query(AuditLog).filter(AuditLog.action == 'privacy.erasure').one()
    assert EMAIL not in json.dumps(event.details) and event.details['deleted']['resumes'] == 1


def test_failed_object_deletion_is_retried_by_retention(client, db, monkeypatch):
    from backend.app.services.privacy import run_retention
    s3 = FakeS3(fail=True)
    monkeypatch.setattr(resume_storage, 'client', lambda: s3)
    monkeypatch.setenv('RESUME_S3_BUCKET', 'private-resumes')
    seed_footprint(db)
    assert client.delete('/api/v1/profile/me', headers=auth()).json()['objects_pending'] == 1
    tombstone = db.query(ErasureTombstone).one()
    assert tombstone.completed_at is None and tombstone.pending_object_keys
    s3.fail = False
    assert run_retention(db)['erasure_objects_retried'] == 1
    db.refresh(tombstone)
    assert tombstone.completed_at and not tombstone.pending_object_keys


def test_officer_erasure_requires_privacy_permission(client, db):
    target = uid(db, 'other@example.com')
    assert client.delete(f'/api/v1/privacy/users/{target}', headers=auth('viewer@example.com')).status_code == 403
    assert client.delete(f'/api/v1/privacy/users/{target}', headers=auth('officer@example.com')).status_code == 200
    assert db.query(User).filter_by(email='other@example.com').first() is None


def test_retention_purges_expired_records(db):
    from backend.app.services.privacy import run_retention
    user_id = uid(db, EMAIL)
    db.add_all([AuditLog(ts=datetime.utcnow() - timedelta(days=500), trace_id='x' * 32, action='old'),
                AuditLog(ts=datetime.utcnow(), trace_id='y' * 32, action='new'),
                RefreshToken(user_id=user_id, token_hash='c' * 64, family_id='f', expires_at=datetime.utcnow() - timedelta(days=1))])
    db.commit()
    result = run_retention(db)
    assert result['audit_logs'] == 1 and result['refresh_tokens'] == 1
    assert [a.action for a in db.query(AuditLog)] == ['new']


# ── Metrics and governance API ───────────────────────────────────────────────

def test_metrics_endpoint_requires_authorization(client, db, monkeypatch):
    assert client.get('/metrics').status_code == 401
    assert client.get('/metrics', headers=auth()).status_code == 401  # no metrics:read
    monkeypatch.setenv('METRICS_TOKEN', 'scrape-token')
    client.get('/api/v1/rbac/matrix', headers=auth())  # produces a 403 sample
    body = client.get('/metrics', headers={'Authorization': 'Bearer scrape-token'}).text
    for series in ('http_requests_total', 'http_request_duration_seconds_bucket', 'unauthorized_attempts_total',
                   'sanitization_blocks_total', 'ocr_fallback_total', 'pdf_single_page_pass_total', 'db_pool_saturation_ratio'):
        assert series in body, series
    assert 'route="/api/v1/rbac/matrix"' in body
    assert client.get('/metrics', headers=auth('viewer@example.com')).status_code == 200


def test_live_summary_raises_latency_and_probe_alerts(client, db, monkeypatch):
    from backend.app.routes import governance
    kv_store.memory_store().clear()
    for _ in range(3):
        client.get('/api/v1/admin/stats', headers=auth())  # 403 probes
    monkeypatch.setattr(governance, 'P95_ALERT_MS', 0.0)
    monkeypatch.setattr(governance, 'UNAUTHORIZED_ALERT', 3)
    summary = client.get('/api/v1/governance/summary', headers=auth('viewer@example.com')).json()
    assert summary['forbidden_403'] >= 3 and summary['p95_ms'] is not None
    kinds = {a['kind'] for a in summary['alerts']}
    assert {'latency', 'unauthorized_probe'} <= kinds
    assert client.get('/api/v1/governance/summary', headers=auth()).status_code == 403


def test_weekly_reports_in_three_formats_and_rbac(client, db):
    for _ in range(3):
        client.get('/api/v1/auth/me', headers=auth())
    client.get('/api/v1/admin/stats', headers=auth())
    audit.flush()
    headers = auth('viewer@example.com')
    data = client.get('/api/v1/governance/reports/weekly?format=json', headers=headers)
    assert data.status_code == 200 and data.json()['totals']['requests'] >= 4 and data.json()['totals'].get('denied', 0) >= 1
    md = client.get('/api/v1/governance/reports/weekly?format=md', headers=headers)
    assert md.headers['content-type'].startswith('text/markdown') and '# Weekly security & reliability report' in md.text
    csv_body = client.get('/api/v1/governance/reports/weekly?format=csv', headers=headers).text
    assert csv_body.splitlines()[0] == 'section,key,requests,denied,errors,value' and 'route,GET /api/v1/auth/me' in csv_body
    assert client.get('/api/v1/governance/reports/weekly?format=xml', headers=headers).status_code == 422
    assert client.get('/api/v1/governance/reports/weekly', headers=auth()).status_code == 403
    assert client.get('/api/v1/governance/audit', headers=headers).status_code == 403  # viewer: no audit:read
    trail = client.get('/api/v1/governance/audit?outcome=denied', headers=auth('auditor@example.com')).json()
    assert trail and all(r['outcome'] == 'denied' for r in trail) and all(EMAIL not in json.dumps(r) for r in trail)


# ── Concurrency ──────────────────────────────────────────────────────────────

def test_sliding_window_is_exact_under_contention():
    from backend.app.core.rate_limit import hit
    kv_store.memory_store().clear()
    with ThreadPoolExecutor(max_workers=32) as pool:
        results = list(pool.map(lambda _: hit('concurrency-test', 20, 60)[0], range(200)))
    assert sum(results) == 20


def test_audit_writer_keeps_every_record_under_parallel_load(tmp_path, monkeypatch):
    # Realistic setup: a pooled engine and one session per request (the shared
    # single-connection fixture session is not thread-safe by design).
    engine = create_engine(f'sqlite:///{tmp_path}/load.db', connect_args={'check_same_thread': False, 'timeout': 30})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as setup:
        setup.add(User(email=EMAIL, full_name='Ada', hashed_password='x', is_verified=True)); setup.commit()
    monkeypatch.setattr('backend.app.database.SessionLocal', Session)

    def per_request():
        session = Session()
        try:
            yield session
        finally:
            session.close()
    app.dependency_overrides[get_db] = per_request
    reset_rate_limits()
    client = TestClient(app, base_url='https://testserver')
    try:
        with ThreadPoolExecutor(max_workers=16) as pool:
            statuses = list(pool.map(lambda _: client.get('/api/v1/auth/me', headers=auth()).status_code, range(48)))
        audit.flush()
    finally:
        app.dependency_overrides.clear()
    assert statuses.count(200) == 48
    with Session() as check:
        assert check.query(AuditLog).filter(AuditLog.route == '/api/v1/auth/me').count() == 48
    engine.dispose()


def test_concurrent_role_changes_keep_a_super_admin(client, db):
    db.add_all([User(email=f'sa{i}@example.com', hashed_password='x', is_verified=True, role='super_admin') for i in range(2)])
    db.commit()
    ids = [uid(db, f'sa{i}@example.com') for i in range(2)]
    lock = threading.Lock()  # SQLite test DB: serialise like row locks would on PostgreSQL
    def demote(i):
        with lock:
            return client.put(f'/api/v1/rbac/users/{ids[i]}/role', json={'role': None}, headers=auth(f'sa{1 - i}@example.com')).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = sorted(pool.map(demote, range(2)))
    assert db.query(User).filter(User.role == 'super_admin').count() >= 1 and 401 in codes or 409 in codes


# ── OpenTelemetry ────────────────────────────────────────────────────────────

def test_tracing_is_opt_in(monkeypatch):
    from backend.app.core.telemetry import init_tracing
    monkeypatch.delenv('OTEL_EXPORTER_OTLP_ENDPOINT', raising=False)
    assert init_tracing(FastAPI()) is False
    pytest.importorskip('opentelemetry.instrumentation.fastapi')
    monkeypatch.setenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://127.0.0.1:4318')
    assert init_tracing(FastAPI()) is True
