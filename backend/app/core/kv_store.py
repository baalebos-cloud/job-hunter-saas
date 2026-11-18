"""Shared key-value store for rate limits, lockouts and token revocation.

Redis (``REDIS_URL``) in production so limits hold across API replicas.
If Redis is unreachable the process falls back to an in-memory store, which
keeps single-instance protection, and reconnects automatically later.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import defaultdict

logger = logging.getLogger(__name__)
RECONNECT_SECONDS = 30


class MemoryStore:
    backend = 'memory'

    def __init__(self):
        self._lock = threading.Lock()
        self._values: dict[str, tuple[float, str]] = {}
        self._windows: dict[str, list[float]] = defaultdict(list)

    def setex(self, key: str, ttl: int, value: str = '1'):
        with self._lock:
            self._values[key] = (time.time() + max(int(ttl), 1), value)

    def exists(self, key: str) -> bool:
        with self._lock:
            item = self._values.get(key)
            if item and item[0] < time.time():
                self._values.pop(key, None)
                return False
            return item is not None

    def delete(self, *keys: str):
        with self._lock:
            for key in keys:
                self._values.pop(key, None)
                self._windows.pop(key, None)

    def window_count(self, key: str, window: int) -> tuple[int, float]:
        now = time.time()
        with self._lock:
            hits = [t for t in self._windows.get(key, []) if now - t < window]
            self._windows[key] = hits
            return len(hits), (hits[0] if hits else now)

    def window_add(self, key: str, window: int) -> int:
        now = time.time()
        with self._lock:
            hits = [t for t in self._windows.get(key, []) if now - t < window] + [now]
            self._windows[key] = hits
            return len(hits)

    def clear(self):
        with self._lock:
            self._values.clear()
            self._windows.clear()


class RedisStore:
    backend = 'redis'

    def __init__(self, client):
        self.client = client

    def setex(self, key, ttl, value='1'):
        self.client.setex(key, max(int(ttl), 1), value)

    def exists(self, key):
        return bool(self.client.exists(key))

    def delete(self, *keys):
        if keys:
            self.client.delete(*keys)

    def window_count(self, key, window):
        now = time.time()
        pipe = self.client.pipeline()
        pipe.zremrangebyscore(key, 0, now - window)
        pipe.zcard(key)
        pipe.zrange(key, 0, 0, withscores=True)
        _, count, oldest = pipe.execute()
        return int(count), (oldest[0][1] if oldest else now)

    def window_add(self, key, window):
        now = time.time()
        pipe = self.client.pipeline()
        pipe.zremrangebyscore(key, 0, now - window)
        pipe.zadd(key, {f'{now}:{uuid.uuid4().hex[:8]}': now})
        pipe.zcard(key)
        pipe.expire(key, int(window) + 1)
        return int(pipe.execute()[2])

    def clear(self):  # pragma: no cover - never used against shared Redis
        raise RuntimeError('Refusing to clear a shared Redis store.')


_memory = MemoryStore()
_redis_store = None
_last_attempt = 0.0
_lock = threading.Lock()


def get_store():
    """Return the Redis store when reachable, else the in-memory fallback."""
    global _redis_store, _last_attempt
    from backend.app.core.config import settings
    url = getattr(settings, 'REDIS_URL', '')
    if not url or settings.ENVIRONMENT == 'test':
        return _memory
    if _redis_store is not None:
        return _redis_store
    with _lock:
        if _redis_store is None and time.time() - _last_attempt > RECONNECT_SECONDS:
            _last_attempt = time.time()
            try:
                import redis
                client = redis.Redis.from_url(url, socket_connect_timeout=0.5, socket_timeout=0.5)
                client.ping()
                _redis_store = RedisStore(client)
            except Exception as exc:
                logger.warning('kv_store_redis_unavailable error_type=%s; using in-memory fallback', type(exc).__name__)
    return _redis_store or _memory


def mark_redis_failed():
    """Drop a broken Redis connection so the next call falls back/reconnects."""
    global _redis_store
    _redis_store = None


def safe_call(method: str, *args, default=None):
    store = get_store()
    try:
        return getattr(store, method)(*args)
    except Exception as exc:
        if store is _memory:
            raise
        logger.warning('kv_store_operation_failed op=%s error_type=%s', method, type(exc).__name__)
        mark_redis_failed()
        return getattr(_memory, method)(*args) if default is None else default


def memory_store() -> MemoryStore:
    return _memory
