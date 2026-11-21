"""Authenticated-user dependency: JWT signature/expiry, token type,
token_version (password reset / log out everywhere) and jti revocation."""
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.database import get_db
from backend.app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def _unauthorized(reason: str):
    try:
        from backend.app.core.metrics import UNAUTHORIZED_ATTEMPTS
        UNAUTHORIZED_ATTEMPTS.labels(status="401", reason=reason).inc()
    except Exception:
        pass
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials",
                         headers={"WWW-Authenticate": "Bearer"})


def decode_access_token(token: str) -> dict:
    if not settings.SECRET_KEY:
        raise HTTPException(503, "Authentication is not configured")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise _unauthorized("invalid_token")
    # Tokens minted before this change (30-day, no type/jti/tv) are rejected.
    if payload.get("type") != "access" or not payload.get("sub") or not payload.get("jti"):
        raise _unauthorized("legacy_or_malformed")
    return payload


def get_current_user(request: Request, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    from backend.app.services.auth_service import is_access_token_revoked
    payload = decode_access_token(token)
    if is_access_token_revoked(payload["jti"]):
        raise _unauthorized("revoked")
    user = db.query(User).filter(User.email == payload["sub"]).first()
    if user is None:
        raise _unauthorized("unknown_user")
    if int(payload.get("tv", 0)) != int(user.token_version or 0):
        raise _unauthorized("token_version")
    if user.suspended_at is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been suspended.")
    # Exposed to the audit middleware (actor/role) without a second lookup.
    request.state.user = user
    # Plain snapshot for the request audit log, which runs after the database
    # session is closed: a committed, detached ORM user can no longer be read.
    from types import SimpleNamespace
    request.state.actor = SimpleNamespace(id=user.id, email=user.email, role=getattr(user, 'role', None),
                                          is_hr=bool(getattr(user, 'is_hr', False)))
    request.state.token_claims = payload
    return user
