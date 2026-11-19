"""Structured audit trail: JSON log line for every request plus an
append-only database record, written off the request path in batches."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import queue
import re
import threading
import time
from datetime import datetime

logger = logging.getLogger("audit")
_EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
_queue: "queue.Queue[dict]" = queue.Queue(maxsize=10000)
_writer_started = False
_writer_lock = threading.Lock()
FLUSH_SECONDS = 1.0
BATCH_SIZE = 200


def actor_hash(email: str | None) -> str | None:
    """Keyed hash: stable for correlation, not reversible without SECRET_KEY."""
    if not email:
        return None
    from backend.app.core.config import settings
    key = (settings.SECRET_KEY or 'audit').encode()
    return hmac.new(key, email.strip().lower().encode(), hashlib.sha256).hexdigest()[:24]


def redact_email(email: str | None) -> str | None:
    if not email or '@' not in email:
        return None
    local, _, domain = email.strip().lower().partition('@')
    name, _, tld = domain.rpartition('.')
    return f"{local[:1]}***@{(name or domain)[:1]}***.{tld or ''}".rstrip('.')


def redact_text(value: str) -> str:
    return _EMAIL.sub(lambda m: redact_email(m.group(0)) or '[email]', value or '')


def outcome_for(status: int) -> str:
    if status in (401, 403):
        return 'denied'
    if status >= 500:
        return 'error'
    if status >= 400:
        return 'client_error'
    return 'success'


def build_request_entry(*, trace_id, user, method, route, status, latency_ms, ip) -> dict:
    from backend.app.core.client_ip import mask_ip
    email = getattr(user, 'email', None)
    return {
        'ts': datetime.utcnow(), 'trace_id': trace_id, 'kind': 'request', 'action': 'http.request',
        'actor_hash': actor_hash(email), 'actor_display': redact_email(email),
        'actor_role': getattr(user, 'role', None) or ('hr' if getattr(user, 'is_hr', False) else ('user' if user else None)),
        'method': method, 'route': route[:200], 'status': status, 'latency_ms': round(latency_ms, 2),
        'outcome': outcome_for(status), 'ip_masked': mask_ip(ip), 'details': None,
    }


def emit(entry: dict, persist: bool = True):
    """Structured JSON log (stdout -> CloudWatch/Datadog/Loki) + DB queue."""
    log_entry = {**entry, 'ts': entry['ts'].isoformat() + 'Z'}
    logger.info(json.dumps(log_entry, default=str, separators=(',', ':')))
    if persist:
        _ensure_writer()
        try:
            _queue.put_nowait(entry)
        except queue.Full:
            logger.error('audit_queue_full dropping_db_copy trace_id=%s', entry.get('trace_id'))


def record_event(action: str, actor=None, details: dict | None = None, trace_id: str | None = None):
    """Security/admin/privacy event (role change, DSAR export, erasure, ...)."""
    import uuid
    email = getattr(actor, 'email', None)
    safe_details = json.loads(redact_text(json.dumps(details or {}, default=str)))
    emit({'ts': datetime.utcnow(), 'trace_id': trace_id or uuid.uuid4().hex, 'kind': 'event', 'action': action,
          'actor_hash': actor_hash(email), 'actor_display': redact_email(email),
          'actor_role': getattr(actor, 'role', None), 'method': None, 'route': None, 'status': None,
          'latency_ms': None, 'outcome': 'success', 'ip_masked': None, 'details': safe_details})


def _ensure_writer():
    global _writer_started
    if _writer_started:
        return
    with _writer_lock:
        if not _writer_started:
            threading.Thread(target=_writer_loop, name='audit-writer', daemon=True).start()
            _writer_started = True


def _writer_loop():
    while True:
        batch = [_queue.get()]
        deadline = time.monotonic() + FLUSH_SECONDS
        while len(batch) < BATCH_SIZE:
            try:
                batch.append(_queue.get(timeout=max(0.0, deadline - time.monotonic())))
            except queue.Empty:
                break
        _write(batch)
        for _ in batch:
            _queue.task_done()


def _session_factory():
    from backend.app import database
    return database.SessionLocal


def _write(batch):
    from backend.app.models.audit import AuditLog
    session = _session_factory()()
    try:
        session.bulk_insert_mappings(AuditLog, batch)
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.error('audit_db_write_failed rows=%s error_type=%s', len(batch), type(exc).__name__)
    finally:
        session.close()


def flush(timeout: float = 5.0):
    """Block until queued records are written (tests, graceful shutdown)."""
    if not _writer_started:
        return
    end = time.monotonic() + timeout
    while _queue.unfinished_tasks and time.monotonic() < end:
        time.sleep(0.01)
