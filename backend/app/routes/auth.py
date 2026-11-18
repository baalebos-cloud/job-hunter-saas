# =============================================================================
# backend/app/routes/auth.py — sign-up, sign-in, sessions, verification, reset
# =============================================================================
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from backend.app.core.client_ip import client_ip
from backend.app.core.config import settings
from backend.app.core.rate_limit import LoginGuard
from backend.app.database import get_db
from backend.app.dependencies.auth import get_current_user
from backend.app.models.user import User
from backend.app.schemas.user import TokenResponse, UserCreate, UserLogin, UserResponse
from backend.app.services.auth_service import (
    RefreshError, access_token_for, clear_refresh_cookie, hash_password, hash_token, issue_refresh_token,
    new_opaque_token, revoke_access_token, revoke_all_sessions, revoke_family, rotate_refresh_token,
    set_refresh_cookie, verify_and_update_password)
from backend.app.utils.email import send_password_reset_email, send_verification_email, send_welcome_email

router = APIRouter(tags=["Authentication"])
login_guard = LoginGuard('login')
MIN_PASSWORD = 8


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)
    new_password: str = Field(min_length=MIN_PASSWORD, max_length=1024)


def start_session(db: Session, user: User, response: Response, extra: dict | None = None) -> dict:
    """Issue a 15-minute access token and a rotating HttpOnly refresh cookie."""
    raw, _ = issue_refresh_token(db, user)
    db.commit()
    set_refresh_cookie(response, raw)
    return {"access_token": access_token_for(user), "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, **(extra or {})}


def authenticate(db: Session, request: Request, email: str, password: str, guard: LoginGuard = login_guard) -> User:
    ip, email = client_ip(request), (email or '').lower().strip()
    guard.check(ip, email)
    user = db.query(User).filter(User.email == email).first()
    ok, new_hash = verify_and_update_password(password, user.hashed_password) if user else (False, None)
    if not ok:
        guard.failure(ip, email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if new_hash:  # transparently upgrade legacy bcrypt hashes
        user.hashed_password = new_hash
        db.commit()
    guard.success(ip, email)
    return user


# ── SIGNUP ───────────────────────────────────────────────────────────────────
@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(user: UserCreate, request: Request, response: Response, background_tasks: BackgroundTasks,
           db: Session = Depends(get_db)):
    if len(user.password) < MIN_PASSWORD:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    if db.query(User).filter(User.email == user.email.lower().strip()).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Email already registered. Please login instead.")
    raw_token, token_digest = new_opaque_token()
    new_user = User(email=user.email.lower().strip(), full_name=user.full_name.strip(),
                    hashed_password=hash_password(user.password), career_track=user.career_track,
                    country=user.country, is_hr=False, company_name=user.company_name,
                    is_verified=False, verification_token=token_digest)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    background_tasks.add_task(send_verification_email, to_email=new_user.email, token=raw_token,
                              full_name=new_user.full_name or "")
    return start_session(db, new_user, response)


# ── EMAIL VERIFICATION ───────────────────────────────────────────────────────
@router.get("/verify-email")
def verify_email(token: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.verification_token == hash_token(token)).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link.")
    if user.is_verified:
        return {"message": "Email already verified. You're good to go!"}
    user.is_verified = True
    user.verification_token = None
    db.commit()
    background_tasks.add_task(send_welcome_email, to_email=user.email, full_name=user.full_name or "")
    return {"message": "Email verified successfully! Welcome to Baalebos Cloud."}


@router.post("/resend-verification")
def resend_verification(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.is_verified:
        return {"message": "Your email is already verified."}
    raw_token, token_digest = new_opaque_token()
    current_user.verification_token = token_digest
    db.commit()
    if not send_verification_email(to_email=current_user.email, token=raw_token, full_name=current_user.full_name or ""):
        raise HTTPException(503, "Verification email could not be sent. Please retry later or contact support.")
    return {"message": "Verification email accepted for sending. Please check your inbox and spam folder."}


# ── PASSWORD RESET (JSON bodies; tokens stored as SHA-256) ───────────────────
@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Always returns the same response to prevent email enumeration."""
    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if user:
        raw_token, token_digest = new_opaque_token()
        user.reset_token = token_digest
        user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
        db.commit()
        background_tasks.add_task(send_password_reset_email, to_email=user.email, token=raw_token,
                                  full_name=user.full_name or "")
    return {"message": "If that email exists, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.reset_token == hash_token(payload.token)).first()
    if not user or not user.reset_token_expires:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link.")
    if user.reset_token_expires < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Reset link has expired. Please request a new one.")
    user.hashed_password = hash_password(payload.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    revoke_all_sessions(db, user)  # every existing JWT and refresh token stops working
    db.commit()
    clear_refresh_cookie(response)
    return {"message": "Password reset successfully. You can now login with your new password."}


# ── LOGIN / SESSIONS ─────────────────────────────────────────────────────────
@router.post("/login", response_model=TokenResponse)
def login(user: UserLogin, request: Request, response: Response, db: Session = Depends(get_db)):
    return start_session(db, authenticate(db, request, user.email, user.password), response)


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    """Rotate the HttpOnly refresh cookie and return a new access token."""
    raw = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not raw:
        raise HTTPException(status_code=401, detail="No active session.")
    try:
        user, new_raw = rotate_refresh_token(db, raw)
    except RefreshError:
        from fastapi.responses import JSONResponse
        denied = JSONResponse({"detail": "Session expired. Please sign in again."}, status_code=401)
        clear_refresh_cookie(denied)
        return denied
    set_refresh_cookie(response, new_raw)
    return {"access_token": access_token_for(user), "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60}


@router.post("/logout")
def logout(request: Request, response: Response, current_user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    claims = getattr(request.state, "token_claims", {})
    revoke_access_token(claims.get("jti"), claims.get("exp"))
    raw = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if raw:
        from backend.app.models.security import RefreshToken
        record = db.query(RefreshToken).filter(RefreshToken.token_hash == hash_token(raw),
                                               RefreshToken.user_id == current_user.id).first()
        if record:
            revoke_family(db, record.family_id)
            db.commit()
    clear_refresh_cookie(response)
    return {"message": "Signed out."}


@router.post("/logout-all")
def logout_all(response: Response, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    revoke_all_sessions(db, current_user)
    db.commit()
    clear_refresh_cookie(response)
    return {"message": "Signed out of all devices."}


# ── CURRENT USER ─────────────────────────────────────────────────────────────
@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from backend.app.dependencies.roles import is_owner, role_permissions
    permissions = sorted(role_permissions(db, current_user.role)) if current_user.is_verified else []
    return {"id": current_user.id, "email": current_user.email,
            "full_name": current_user.full_name, "career_track": current_user.career_track,
            "country": current_user.country, "is_admin": is_owner(current_user),
            "is_hr": bool(current_user.is_hr and current_user.is_verified and current_user.hr_approved),
            "role": current_user.role, "permissions": permissions}


# ── ADMIN LOGIN ──────────────────────────────────────────────────────────────
@router.post("/admin/login")
def admin_login(user: UserLogin, request: Request, response: Response, db: Session = Depends(get_db)):
    from backend.app.dependencies.roles import has_permission
    db_user = authenticate(db, request, user.email, user.password, LoginGuard('admin'))
    if not has_permission(db, db_user, 'admin:access'):
        LoginGuard('admin').failure(client_ip(request), user.email)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied. Admin account required.")
    return start_session(db, db_user, response, {"is_admin": True, "email": db_user.email,
                                                  "full_name": db_user.full_name, "redirect": "/admin"})
