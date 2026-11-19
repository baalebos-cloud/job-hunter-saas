"""Sliding-window rate limits and credential-stuffing lockouts.

Counters live in the shared store (Redis), keyed by the trusted client IP
and, for logins, by a hash of the normalised email as well, so rotating IPs
cannot brute-force one account and one IP cannot spray many accounts.
"""
from __future__ import annotations

import hashlib
import math
import time

from fastapi import HTTPException, status

from backend.app.core.kv_store import safe_call

LOGIN_MAX_FAILURES_PER_IP = 10
LOGIN_MAX_FAILURES_PER_EMAIL = 5
LOGIN_LOCKOUT_SECONDS = 300


def _email_key(email: str) -> str:
    return hashlib.sha256((email or '').strip().casefold().encode()).hexdigest()[:32]


def hit(key: str, limit: int, window: int) -> tuple[bool, int]:
    """Record one request; return (allowed, retry_after_seconds)."""
    count = safe_call('window_add', f'rl:{key}', window)
    if count > limit:
        _, oldest = safe_call('window_count', f'rl:{key}', window)
        return False, max(1, math.ceil(window - (time.time() - oldest)))
    return True, 0


class LoginGuard:
    def __init__(self, scope: str = 'login'):
        self.scope = scope

    def _keys(self, ip: str, email: str):
        return f'bf:{self.scope}:ip:{ip}', f'bf:{self.scope}:email:{_email_key(email)}'

    def check(self, ip: str, email: str):
        ip_key, email_key = self._keys(ip, email)
        ip_count, ip_oldest = safe_call('window_count', ip_key, LOGIN_LOCKOUT_SECONDS)
        email_count, email_oldest = safe_call('window_count', email_key, LOGIN_LOCKOUT_SECONDS)
        if ip_count >= LOGIN_MAX_FAILURES_PER_IP or email_count >= LOGIN_MAX_FAILURES_PER_EMAIL:
            oldest = min(ip_oldest, email_oldest)
            remaining = max(1, int(LOGIN_LOCKOUT_SECONDS - (time.time() - oldest)))
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail=f'Too many failed attempts. Try again in {remaining} seconds.',
                                headers={'Retry-After': str(remaining)})

    def failure(self, ip: str, email: str):
        for key in self._keys(ip, email):
            safe_call('window_add', key, LOGIN_LOCKOUT_SECONDS)

    def success(self, ip: str, email: str):
        # Clear the account counter; the IP counter keeps limiting sprays.
        safe_call('delete', self._keys(ip, email)[1])
