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

import threading
import time
from contextlib import contextmanager

from fastapi import HTTPException

from backend.app.core.config import settings


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
    """Pro and Enterprise subscribers, and the owner / verified admins."""
    from backend.app.dependencies.plan_guard import effective_plan
    from backend.app.models.subscription import Subscription
    sub = db.query(Subscription).filter(Subscription.user_id == user.id).first()
    return effective_plan(user, sub.plan if sub else None, sub.status if sub else None) in ("pro", "enterprise")


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
