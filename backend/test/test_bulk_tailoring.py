"""Bulk resume processing (Enterprise): one resume tailored to up to 10 jobs."""
import json

import pytest

from backend.app.core.config import settings
from backend.app.models.job import Job
from backend.app.models.resume import Resume
from backend.app.models.subscription import Subscription
from backend.app.utils.pdf_generator import export_resume
from backend.test.test_scaling import AUTH, BASE, client, db, pipeline  # noqa: F401

JD = 'We need Python and Terraform skills for this platform engineering role, building internal tools.'


def enterprise(db):
    db.add(Subscription(user_id=1, plan='enterprise', status='active'))
    db.commit()


def jobs(db, n):
    rows = [Job(title=f'Platform Engineer {i}', company=f'Company {i}', description=JD, is_active=True) for i in range(n)]
    db.add_all(rows); db.commit()
    return [j.id for j in rows]


def bulk(client, **data):
    return client.post('/api/v1/resume/bulk', headers=AUTH, data=data,
                       files={'file': ('cv.pdf', export_resume(BASE).pdf, 'application/pdf')})


def test_bulk_tailoring_is_an_enterprise_feature(client, db, pipeline):
    ids = jobs(db, 2)
    denied = bulk(client, job_ids=','.join(map(str, ids)))
    assert denied.status_code == 403 and denied.json()['detail']['error'] == 'enterprise_required'
    db.add(Subscription(user_id=1, plan='pro', status='active')); db.commit()
    assert bulk(client, job_ids=str(ids[0])).status_code == 403


def test_one_resume_tailored_to_board_and_pasted_jobs(client, db, pipeline):
    enterprise(db)
    ids = jobs(db, 2)
    pasted = json.dumps([{'title': 'Data Engineer', 'description': JD},
                         {'title': 'Too short', 'description': 'tiny'}])           # ignored: no real description
    started = bulk(client, job_ids=f'{ids[0]},{ids[1]},999999', pasted_jobs=pasted)
    assert started.status_code == 202 and started.json()['count'] == 3
    status = client.get(f"/api/v1/resume/bulk/{started.json()['batch_id']}", headers=AUTH).json()
    assert status['done'] == status['total'] == 3
    assert [i['status'] for i in status['items']] == ['completed'] * 3
    assert [i['company'] for i in status['items']] == ['Company 0', 'Company 1', None]
    assert all(isinstance(i['score_after'], (int, float)) for i in status['items'])
    history = client.get('/api/v1/resume/history', headers=AUTH).json()
    assert {i['job_title'] for i in history['items']} >= {'Platform Engineer 0', 'Platform Engineer 1', 'Data Engineer'}


def test_limits_and_validation(client, db, pipeline):
    enterprise(db)
    ids = jobs(db, 11)
    assert bulk(client, job_ids=','.join(map(str, ids))).status_code == 400            # more than 10
    assert bulk(client).status_code == 400                                              # nothing chosen
    assert client.get('/api/v1/resume/bulk/not-a-batch', headers=AUTH).status_code == 404


def test_one_failed_job_does_not_stop_the_others(client, db, pipeline, monkeypatch):
    import backend.app.utils.ats_engine as engine
    enterprise(db)
    ids = jobs(db, 2)
    real = engine.extract_requirements
    calls = {'n': 0}

    def flaky(jd):
        calls['n'] += 1
        if calls['n'] == 1:
            raise RuntimeError('provider down')
        return real(jd)
    monkeypatch.setattr(engine, 'extract_requirements', flaky)
    batch = bulk(client, job_ids=f'{ids[0]},{ids[1]}').json()['batch_id']
    items = client.get(f'/api/v1/resume/bulk/{batch}', headers=AUTH).json()['items']
    assert [i['status'] for i in items] == ['failed', 'completed']
    assert 'Reference' in items[0]['error'] and 'provider down' not in items[0]['error']


def test_async_mode_queues_every_job_with_priority(client, db, pipeline, monkeypatch):
    from backend.app.tasks import resume_tasks
    enterprise(db)
    ids = jobs(db, 3)
    monkeypatch.setattr(settings, 'RESUME_PROCESSING_MODE', 'async')
    sent = []
    monkeypatch.setattr(resume_tasks.process_resume_upload, 'apply_async', lambda **kw: sent.append(kw))
    batch = bulk(client, job_ids=','.join(map(str, ids))).json()['batch_id']
    assert len(sent) == 3 and {s['priority'] for s in sent} == {0}
    assert all(s['kwargs']['job_meta']['batch_id'] == batch for s in sent)
    assert db.query(Resume).filter(Resume.status == 'processing').count() == 3
