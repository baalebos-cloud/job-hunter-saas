"""Async mode only queues work when a Celery worker is alive; otherwise it tailors in the API."""
import time

from backend.app.core.config import settings
from backend.app.services import processing_gate
from backend.test.test_scaling import AUTH, client, db, pipeline, upload  # noqa: F401


def reset(monkeypatch, ping):
    monkeypatch.setattr(processing_gate, '_worker_state', {'at': -1e9, 'ok': False})
    monkeypatch.setattr(processing_gate, '_ping_workers', ping)


def test_no_worker_means_the_upload_is_tailored_right_away(client, db, pipeline, monkeypatch):
    monkeypatch.setattr(settings, 'RESUME_PROCESSING_MODE', 'async')
    reset(monkeypatch, lambda timeout=1.0: False)
    from backend.app.tasks import resume_tasks
    queued = []
    monkeypatch.setattr(resume_tasks.process_resume_upload, 'apply_async', lambda **kw: queued.append(kw))
    response = upload(client)
    assert response.status_code == 200 and response.json()['status'] == 'completed'
    assert queued == []


def test_a_live_worker_gets_the_job(client, db, pipeline, monkeypatch):
    monkeypatch.setattr(settings, 'RESUME_PROCESSING_MODE', 'async')
    reset(monkeypatch, lambda timeout=1.0: True)
    from backend.app.tasks import resume_tasks
    queued = []
    monkeypatch.setattr(resume_tasks.process_resume_upload, 'apply_async', lambda **kw: queued.append(kw))
    response = upload(client)
    assert response.status_code == 202 and len(queued) == 1


def test_sync_mode_never_pings(monkeypatch):
    monkeypatch.setattr(settings, 'RESUME_PROCESSING_MODE', 'sync')
    reset(monkeypatch, lambda timeout=1.0: (_ for _ in ()).throw(AssertionError('pinged')))
    assert processing_gate.use_async_queue() is False


def test_worker_check_is_cached_and_bounded(monkeypatch):
    calls = []
    reset(monkeypatch, lambda timeout=1.0: calls.append(1) or True)
    assert processing_gate.async_workers_available() and processing_gate.async_workers_available()
    assert len(calls) == 1                                   # cached for 30 seconds

    def hang(timeout=1.0):
        time.sleep(5)
        return True
    reset(monkeypatch, hang)
    started = time.monotonic()
    assert processing_gate.async_workers_available() is False   # a dead broker cannot stall a request
    assert time.monotonic() - started < 3


def test_a_broken_broker_counts_as_no_worker(monkeypatch):
    def broken(timeout=1.0):
        raise ConnectionError('redis down')
    reset(monkeypatch, broken)
    assert processing_gate.async_workers_available() is False
