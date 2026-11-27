"""Priority AI processing for paid plans, and My resumes (history)."""
import json
import threading
import time
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db, get_read_db
from backend.app.main import app
from backend.app.models.job import Job
from backend.app.models.registry import import_all_models
from backend.app.models.resume import Resume
from backend.app.models.subscription import Subscription
from backend.app.models.user import User
from backend.app.services import audit, security_events
from backend.app.services.auth_service import create_access_token
from backend.app.services.processing_gate import ProcessingGate, has_priority
from backend.app.utils import ats_engine


@pytest.fixture
def db(monkeypatch):
    import_all_models()
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_read_db] = lambda: session
    monkeypatch.setattr(security_events, '_session', Session)
    monkeypatch.setattr('backend.app.database.SessionLocal', Session)
    session.add_all([User(id=1, email='free@example.com', hashed_password='x', is_verified=True),
                     User(id=2, email='pro@example.com', hashed_password='x', is_verified=True),
                     User(id=3, email='owner@example.com', hashed_password='x', is_verified=True, is_admin=True,
                          role='super_admin'),
                     Subscription(user_id=2, plan='pro', status='active')])
    session.commit()
    yield session
    audit.flush()
    app.dependency_overrides.clear()
    session.close()
    engine.dispose()


def auth(email):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': email})}


# ── Priority processing ──────────────────────────────────────────────────────

def test_free_users_cannot_use_the_reserved_slot_but_paid_users_can():
    gate = ProcessingGate(total=2, reserved=1)
    assert gate.acquire(priority=False, timeout=0.05)              # free takes the shared slot
    assert not gate.acquire(priority=False, timeout=0.05)          # reserved slot is not for free users
    assert gate.acquire(priority=True, timeout=0.05)               # paid user gets the reserved slot
    assert not gate.acquire(priority=True, timeout=0.05)           # full
    gate.release(); gate.release()
    assert gate.in_use == 0


def test_a_waiting_paid_user_is_served_before_a_waiting_free_user():
    gate = ProcessingGate(total=1, reserved=0)
    assert gate.acquire(priority=False, timeout=0.05)
    order = []

    def wait(priority, label):
        if gate.acquire(priority=priority, timeout=2):
            order.append(label)
            time.sleep(0.05)
            gate.release()
    free = threading.Thread(target=wait, args=(False, 'free')); free.start()
    time.sleep(0.05)                                               # the free user is already waiting
    paid = threading.Thread(target=wait, args=(True, 'paid')); paid.start()
    time.sleep(0.05)
    gate.release()                                                 # one slot frees up
    free.join(); paid.join()
    assert order == ['paid', 'free']


def test_priority_is_for_pro_enterprise_and_the_owner(db):
    assert not has_priority(db, db.get(User, 1))
    assert has_priority(db, db.get(User, 2))
    assert has_priority(db, db.get(User, 3))
    db.query(Subscription).filter_by(user_id=2).one().status = 'cancelled'; db.commit()
    assert not has_priority(db, db.get(User, 2))


def _rate_limited(retry_after):
    import httpx
    from openai import RateLimitError
    response = httpx.Response(429, headers={'retry-after': retry_after}, request=httpx.Request('POST', 'https://x.test'))
    return RateLimitError('rate limited', response=response, body=None)


def _client(outcomes, calls):
    def create(**kwargs):
        calls.append(kwargs['model'])
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop', message=SimpleNamespace(content=outcome))],
                               usage=SimpleNamespace(completion_tokens=5))
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


@pytest.mark.parametrize('priority, expected_sleeps, expected_models', [
    (False, [3.5], ['primary-model', 'primary-model']),            # free: waits for the primary
    (True, [], ['primary-model', 'backup-model']),                 # paid: switches to the backup at once
])
def test_paid_runs_fail_over_to_the_backup_provider_without_waiting(monkeypatch, priority, expected_sleeps, expected_models):
    calls, slept = [], []
    primary = _client([_rate_limited('3'), '{"ok": 1}'], calls)
    backup = _client(['{"ok": 2}'], calls)
    monkeypatch.setattr(ats_engine, 'get_client', lambda: (primary, 'primary-model'))
    monkeypatch.setattr(ats_engine, 'provider_chain', lambda: [('groq', primary, 'primary-model'),
                                                              ('openrouter', backup, 'backup-model')])
    monkeypatch.setattr(ats_engine.time, 'sleep', slept.append)
    token = ats_engine.PRIORITY_RUN.set(priority)
    try:
        assert ats_engine._json('Return JSON.') in ({'ok': 1}, {'ok': 2})
    finally:
        ats_engine.PRIORITY_RUN.reset(token)
    assert slept == expected_sleeps and calls == expected_models


def test_paid_jobs_are_queued_ahead_of_free_ones(db, monkeypatch):
    from backend.app.routes import resume as routes
    from backend.app.tasks import resume_tasks
    sent = []
    monkeypatch.setattr(resume_tasks.process_resume_upload, 'apply_async', lambda **kw: sent.append(kw))
    routes._enqueue(db, db.get(User, 2), 'paid-task', b'%PDF', 'cv.pdf', 'JD', 'DevOps', 'NG', True, {'job_id': 7})
    routes._enqueue(db, db.get(User, 1), 'free-task', b'%PDF', 'cv.pdf', 'JD', 'DevOps', 'NG', False, {})
    assert [s['priority'] for s in sent] == [0, 6]
    assert sent[0]['kwargs'] == {'priority': True, 'job_meta': {'job_id': 7}}


# ── My resumes ───────────────────────────────────────────────────────────────

def _resumes(db, owner_id, count):
    start = datetime(2026, 11, 1)
    for i in range(count):
        db.add(Resume(owner_id=owner_id, filename=f'optimized_t{owner_id}-{i}.pdf', status='completed', content=b'%PDF-1.4',
                      created_at=start + timedelta(hours=i), parsed_data=json.dumps({'name': 'X'}),
                      analysis_data={'job_title': f'Role {i}', 'company': 'Contoso', 'job_id': 5,
                                     'scores': {'before': 50, 'after': 80}, 'job_description': 'Kubernetes'}))
    db.add(Resume(owner_id=owner_id, filename=f'optimized_t{owner_id}-failed.pdf', status='failed'))
    db.commit()


def test_history_keeps_the_last_30_for_paid_and_the_latest_for_free(db):
    _resumes(db, 1, 3)
    _resumes(db, 2, 35)
    client = TestClient(app)
    free = client.get('/api/v1/resume/history', headers=auth('free@example.com')).json()
    assert free['history_enabled'] is False and free['limit'] == 1 and free['total'] == 3
    assert [i['job_title'] for i in free['items']] == ['Role 2']                # newest only
    paid = client.get('/api/v1/resume/history', headers=auth('pro@example.com')).json()
    assert paid['history_enabled'] is True and paid['limit'] == 30 and len(paid['items']) == 30 and paid['total'] == 35
    first = paid['items'][0]
    assert first['task_id'] == 't2-34' and first['company'] == 'Contoso' and first['job_id'] == 5
    assert (first['score_before'], first['score_after']) == (50, 80)
    assert all('failed' not in i['task_id'] for i in paid['items'])


def test_a_resume_can_be_deleted_by_its_owner_only(db):
    _resumes(db, 1, 1)
    client = TestClient(app)
    assert client.delete('/api/v1/resume/t1-0', headers=auth('pro@example.com')).status_code == 404
    assert client.delete('/api/v1/resume/t1-0', headers=auth('free@example.com')).json() == {'deleted': True}
    assert db.query(Resume).filter_by(filename='optimized_t1-0.pdf').count() == 0


def test_job_meta_records_the_job_and_company(db):
    from backend.app.routes.resume import _job_meta
    db.add(Job(id=9, title='SRE', company='Northwind', is_active=True)); db.commit()
    assert _job_meta(db, 9) == {'job_id': 9, 'company': 'Northwind'}
    assert _job_meta(db, None) == {} and _job_meta(db, 404) == {}


def test_a_chosen_page_length_reaches_the_worker(db, monkeypatch):
    from backend.app.routes import resume as routes
    from backend.app.tasks import resume_tasks
    sent = []
    monkeypatch.setattr(resume_tasks.process_resume_upload, 'apply_async', lambda **kw: sent.append(kw))
    routes._enqueue(db, db.get(User, 2), 'two-pages', b'%PDF', 'cv.pdf', 'JD', 'DevOps', 'US', True, {}, 2)
    assert sent[0]['kwargs'] == {'priority': True, 'job_meta': {}, 'max_pages': 2}
