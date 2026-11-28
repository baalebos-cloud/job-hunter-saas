"""Priority AI processing for paid plans.

Resume tailoring is the heavy step (several AI calls plus PDF rendering). The
gate caps how many run at once in this process and keeps part of that
capacity for paying customers:

* Pro / Enterprise (and the owner) may use every slot, and when a slot frees
  up they are served before any waiting free user.
* Free users may only use the unreserved slots; when those are busy they wait
  in line, then get a clear "busy, retry shortly" message instead of a hang.

Paid runs are also marked as priority for the AI client, which then switches
to the backup provider straight away on a rate limit instead of waiting.
"""
from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager

from fastapi import HTTPException

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class ProcessingGate:
    def __init__(self, total: int, reserved: int):
        self.total = max(1, int(total))
        self.reserved = min(max(0, int(reserved)), self.total - 1)
        self.in_use = 0
        self.priority_waiting = 0
        self._cond = threading.Condition()

    def _free_slot(self, priority: bool) -> bool:
        if priority:
            return self.in_use < self.total
        # Free users never take a reserved slot, and always yield to a waiting paid user.
        return self.in_use < self.total - self.reserved and self.priority_waiting == 0

    def acquire(self, priority: bool, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        with self._cond:
            if priority:
                self.priority_waiting += 1
            try:
                while not self._free_slot(priority):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return False
                    self._cond.wait(remaining)
                self.in_use += 1
                return True
            finally:
                if priority:
                    self.priority_waiting -= 1
                    self._cond.notify_all()

    def release(self) -> None:
        with self._cond:
            self.in_use = max(0, self.in_use - 1)
            self._cond.notify_all()


_gate = ProcessingGate(settings.RESUME_MAX_CONCURRENT, settings.RESUME_PRIORITY_RESERVED)


def gate() -> ProcessingGate:
    return _gate


def has_priority(db, user) -> bool:
    """Pro and Enterprise subscribers (including Enterprise team members), and the owner / verified admins."""
    from backend.app.dependencies.plan_guard import plan_for
    return plan_for(db, user) in ("pro", "enterprise")


@contextmanager
def processing_slot(priority: bool):
    """Hold a processing slot for the duration of one tailoring run."""
    timeout = settings.RESUME_PRIORITY_WAIT_SECONDS if priority else settings.RESUME_FREE_WAIT_SECONDS
    if not _gate.acquire(priority, timeout):
        raise HTTPException(503, "Resume tailoring is busy right now. Please try again in a minute. Nothing was charged.",
                            headers={"Retry-After": "60"})
    try:
        yield
    finally:
        _gate.release()


# ── Async queue health ───────────────────────────────────────────────────────
# RESUME_PROCESSING_MODE=async hands tailoring to Celery workers (202 + polling).
# If no worker answers, queued resumes would sit in "processing" until they
# expire, so requests are tailored in the API process instead, as in sync mode.
_WORKER_CHECK_TTL = 30.0
_worker_state = {'at': -1e9, 'ok': False}
_worker_lock = threading.Lock()


def _ping_workers(timeout: float = 1.0) -> bool:
    from backend.app.celery_app import celery_app
    return bool(celery_app.control.ping(timeout=timeout))


def async_workers_available() -> bool:
    """True when at least one Celery worker answered a ping in the last 30 seconds."""
    import concurrent.futures
    now = time.monotonic()
    with _worker_lock:
        if now - _worker_state['at'] < _WORKER_CHECK_TTL:
            return _worker_state['ok']
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        ok = pool.submit(_ping_workers).result(timeout=2.0)   # a dead broker cannot stall the request
    except Exception:
        ok = False
    finally:
        pool.shutdown(wait=False)
    with _worker_lock:
        _worker_state.update(at=time.monotonic(), ok=ok)
    if not ok:
        logger.warning('resume_async_no_worker fallback=sync')
    return ok


def use_async_queue() -> bool:
    """Queue tailoring on Celery only in async mode and only with a live worker."""
    return settings.RESUME_PROCESSING_MODE == 'async' and async_workers_available()
