"""Two-step verification with authenticator apps (TOTP, RFC 6238).

* The shared secret is encrypted at rest (Fernet, key derived from SECRET_KEY).
* Codes are 6 digits, 30-second steps, ±1 step of clock drift; a code is
  accepted once only (replay protection).
* 10 single-use recovery codes, stored as SHA-256 hashes.
* Sign-in with 2FA is two steps: password -> short-lived signed ``mfa`` token
  -> code. Admin console access requires 2FA when ADMIN_2FA_REQUIRED is on.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
import uuid
from datetime import datetime, timedelta
from urllib.parse import quote

ISSUER = 'Baalebos Cloud'
STEP = 30
DIGITS = 6
MFA_TOKEN_MINUTES = 5
RECOVERY_CODES = 10


def admin_2fa_required() -> bool:
    return os.getenv('ADMIN_2FA_REQUIRED', 'true').strip().lower() not in ('0', 'false', 'no', 'off')


def _fernet():
    from cryptography.fernet import Fernet
    from backend.app.core.config import settings
    key = hashlib.sha256(('totp:' + (settings.SECRET_KEY or '')).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_secret(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')


def otpauth_uri(secret: str, account: str) -> str:
    return (f'otpauth://totp/{quote(ISSUER)}:{quote(account)}?secret={secret}'
            f'&issuer={quote(ISSUER)}&algorithm=SHA1&digits={DIGITS}&period={STEP}')


def totp(secret: str, counter: int) -> str:
    key = base64.b32decode(secret + '=' * (-len(secret) % 8), casefold=True)
    digest = hmac.new(key, struct.pack('>Q', counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10 ** DIGITS).zfill(DIGITS)


def verify_code(user, code: str, secret: str | None = None, now: float | None = None) -> bool:
    """Check a 6-digit code against the user's (or a pending) secret, once only."""
    from backend.app.core.kv_store import safe_call
    code = ''.join(ch for ch in (code or '') if ch.isdigit())
    if len(code) != DIGITS:
        return False
    try:
        secret = secret or decrypt_secret(user.totp_secret)
    except Exception:
        return False
    counter = int((now or time.time()) // STEP)
    for step in (counter - 1, counter, counter + 1):
        if hmac.compare_digest(totp(secret, step), code):
            used = f'mfa:used:{user.id}:{step}'
            if safe_call('exists', used, default=False):
                return False
            safe_call('setex', used, STEP * 3, '1')
            return True
    return False


def _hash(code: str) -> str:
    return hashlib.sha256(code.replace('-', '').strip().lower().encode()).hexdigest()


def new_recovery_codes(user) -> list[str]:
    codes = [f'{secrets.token_hex(2)}-{secrets.token_hex(2)}-{secrets.token_hex(2)}' for _ in range(RECOVERY_CODES)]
    user.totp_recovery_codes = [_hash(c) for c in codes]
    return codes


def use_recovery_code(user, code: str) -> bool:
    stored = list(user.totp_recovery_codes or [])
    digest = _hash(code or '')
    if digest in stored:
        stored.remove(digest)
        user.totp_recovery_codes = stored     # reassign so the JSON column is saved
        return True
    return False


def issue_mfa_token(user, extra: dict | None = None) -> str:
    from jose import jwt
    from backend.app.core.config import settings
    claims = {'sub': user.email, 'type': 'mfa', 'jti': str(uuid.uuid4()), 'tv': int(user.token_version or 0),
              'exp': datetime.utcnow() + timedelta(minutes=MFA_TOKEN_MINUTES), 'x': extra or {}}
    return jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def read_mfa_token(token: str) -> dict | None:
    from jose import JWTError, jwt
    from backend.app.core.config import settings
    try:
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
    return claims if claims.get('type') == 'mfa' and claims.get('sub') else None
