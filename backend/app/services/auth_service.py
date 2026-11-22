"""Password hashing, access/refresh tokens and revocation.

* Passwords: bcrypt over an HMAC-SHA256 pre-hash (passlib ``bcrypt_sha256``),
  so every byte of long or multi-byte UTF-8 passwords counts (plain bcrypt
  silently truncates at 72 bytes). Legacy plain-bcrypt hashes still verify
  and are upgraded on the next successful login.
* Access tokens: 15-minute JWTs carrying ``jti``, ``tv`` (token_version) and
  ``type``; revocable via the shared store until they expire.
* Refresh tokens: random, stored only as SHA-256, rotated on every use, with
  reuse detection that revokes the whole token family.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta

from fastapi import HTTPException
import jwt
from passlib.context import CryptContext

from backend.app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt_sha256", "bcrypt"], deprecated=["bcrypt"])
MAX_PASSWORD_CHARS = 1024  # bounds hashing cost; far above any real password


# ── Passwords ────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    if not password:
        raise HTTPException(status_code=400, detail="Password cannot be empty")
    if len(password) > MAX_PASSWORD_CHARS:
        raise HTTPException(status_code=400, detail="Password is too long")
    return pwd_context.hash(password)


def verify_and_update_password(plain_password: str, hashed_password: str) -> tuple[bool, str | None]:
    """Return (valid, new_hash). ``new_hash`` is set when a legacy hash should
    be replaced with the current scheme."""
    if not plain_password or not hashed_password or len(plain_password) > MAX_PASSWORD_CHARS:
        return False, None
    try:
        return pwd_context.verify_and_update(plain_password, hashed_password)
    except (ValueError, TypeError):
        pass
    # Legacy hashes were created from password[:72] (characters) by plain bcrypt.
    try:
        if pwd_context.identify(hashed_password) == 'bcrypt':
            ok = pwd_context.verify(plain_password[:72], hashed_password)
            return ok, (pwd_context.hash(plain_password) if ok else None)
    except (ValueError, TypeError):
        pass
    return False, None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return verify_and_update_password(plain_password, hashed_password)[0]


# ── Opaque tokens (email verification, password reset, refresh) ──────────────

def hash_token(raw: str) -> str:
    return hashlib.sha256(str(raw or '').encode('utf-8')).hexdigest()


def new_opaque_token() -> tuple[str, str]:
    """Return (raw, sha256) - send the raw value, store only the hash."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


# ── Access tokens ────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    if not settings.SECRET_KEY:
        raise HTTPException(503, "Authentication is not configured")
    now = datetime.utcnow()
    claims = {
        **data,
        "type": "access",
        "tv": int(data.get("tv", 0) or 0),
        "jti": data.get("jti") or uuid.uuid4().hex,
        "iat": now,
        "exp": now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)),
    }
    return jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def access_token_for(user) -> str:
    return create_access_token({"sub": user.email, "tv": user.token_version or 0})


def revoke_access_token(jti: str, exp: int | float | None):
    """Block a specific access token until it would have expired anyway."""
    from backend.app.core.kv_store import safe_call
    if not jti:
        return
    ttl = int((exp or 0) - datetime.utcnow().timestamp()) if exp else settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    if ttl > 0:
        safe_call('setex', f'auth:revoked:{jti}', ttl, '1')


def is_access_token_revoked(jti: str) -> bool:
    from backend.app.core.kv_store import safe_call
    return bool(jti) and bool(safe_call('exists', f'auth:revoked:{jti}', default=False))


# ── Refresh tokens ───────────────────────────────────────────────────────────

def issue_refresh_token(db, user, family_id: str | None = None):
    from backend.app.models.security import RefreshToken
    raw, digest = new_opaque_token()
    record = RefreshToken(user_id=user.id, token_hash=digest, family_id=family_id or str(uuid.uuid4()),
                          expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))
    db.add(record)
    db.flush()
    return raw, record


class RefreshError(Exception):
    pass


def rotate_refresh_token(db, raw: str):
    """Exchange a refresh token for (user, new_raw). Reuse of a rotated token
    revokes every token in its family and invalidates outstanding JWTs."""
    from backend.app.models.security import RefreshToken
    from backend.app.models.user import User
    record = db.query(RefreshToken).filter(RefreshToken.token_hash == hash_token(raw)).with_for_update().first()
    if record is None:
        raise RefreshError('unknown')
    now = datetime.utcnow()
    user = db.query(User).filter(User.id == record.user_id).first()
    if record.revoked_at is not None:
        revoke_family(db, record.family_id)
        if user is not None:
            user.token_version = (user.token_version or 0) + 1
        db.commit()
        raise RefreshError('reused')
    if record.expires_at < now or user is None:
        record.revoked_at = now
        db.commit()
        raise RefreshError('expired')
    new_raw, new_record = issue_refresh_token(db, user, record.family_id)
    record.revoked_at = now
    record.replaced_by_id = new_record.id
    db.commit()
    return user, new_raw


def revoke_family(db, family_id: str):
    from backend.app.models.security import RefreshToken
    db.query(RefreshToken).filter(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None)) \
        .update({RefreshToken.revoked_at: datetime.utcnow()}, synchronize_session=False)


def revoke_all_sessions(db, user):
    """Log out everywhere: bump token_version and revoke all refresh tokens."""
    from backend.app.models.security import RefreshToken
    user.token_version = (user.token_version or 0) + 1
    db.query(RefreshToken).filter(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)) \
        .update({RefreshToken.revoked_at: datetime.utcnow()}, synchronize_session=False)


def set_refresh_cookie(response, raw: str):
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME, raw, max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        httponly=True, secure=settings.REFRESH_COOKIE_SECURE or settings.REFRESH_COOKIE_SAMESITE == 'none',
        samesite=settings.REFRESH_COOKIE_SAMESITE, path=settings.REFRESH_COOKIE_PATH,
        domain=settings.REFRESH_COOKIE_DOMAIN or None)


def clear_refresh_cookie(response):
    response.delete_cookie(settings.REFRESH_COOKIE_NAME, path=settings.REFRESH_COOKIE_PATH,
                           domain=settings.REFRESH_COOKIE_DOMAIN or None,
                           secure=settings.REFRESH_COOKIE_SECURE, httponly=True,
                           samesite=settings.REFRESH_COOKIE_SAMESITE)

