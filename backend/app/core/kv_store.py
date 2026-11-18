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
        self._lock = threading.RLock()
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

    def incr(self, key: str, amount: int = 1, ttl: int = 3600) -> int:
        with self._lock:
            expires, value = self._values.get(key, (0, '0'))
            if expires and expires < time.time():
                value = '0'
            new = int(value) + amount
            self._values[key] = (time.time() + ttl, str(new))
            return new

    def get(self, key: str):
        with self._lock:
            item = self._values.get(key)
            if not item or item[0] < time.time():
                return None
            return item[1]

    def push_sample(self, key: str, value: float, maxlen: int = 1000, ttl: int = 3600):
        with self._lock:
            samples = self._windows[key]
            samples.append(float(value))
            del samples[:-maxlen]
            self._values[f'{key}:ttl'] = (time.time() + ttl, '1')

    def samples(self, key: str) -> list[float]:
        with self._lock:
            marker = self._values.get(f'{key}:ttl')
            if marker and marker[0] < time.time():
                self._windows.pop(key, None)
                self._values.pop(f'{key}:ttl', None)
            return list(self._windows.get(key, []))

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

    def incr(self, key, amount=1, ttl=3600):
        pipe = self.client.pipeline()
        pipe.incrby(key, amount)
        pipe.expire(key, ttl)
        return int(pipe.execute()[0])

    def get(self, key):
        value = self.client.get(key)
        return value.decode() if isinstance(value, bytes) else value

    def push_sample(self, key, value, maxlen=1000, ttl=3600):
        pipe = self.client.pipeline()
        pipe.lpush(key, float(value))
        pipe.ltrim(key, 0, maxlen - 1)
        pipe.expire(key, ttl)
        pipe.execute()

    def samples(self, key):
        return [float(v) for v in self.client.lrange(key, 0, -1)]

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
