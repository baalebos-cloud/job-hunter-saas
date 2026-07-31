# =============================================================================
# backend/app/routes/auth.py — wired with email verification + password reset
# =============================================================================
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from collections import defaultdict
import time

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.schemas.user import UserCreate, UserLogin, TokenResponse, UserResponse
from backend.app.services.auth_service import hash_password, verify_password, create_access_token
from backend.app.dependencies.auth import get_current_user

# ── NEW: import email utilities ───────────────────────────────────────────────
from backend.app.utils.email import (
    send_verification_email,
    send_welcome_email,
    send_password_reset_email,
)

router = APIRouter(tags=["Authentication"])

# Brute force protection
_failed_attempts: dict = defaultdict(list)
MAX_ATTEMPTS    = 5
LOCKOUT_SECONDS = 300


def _check_brute_force(ip: str):
    now = time.time()
    _failed_attempts[ip] = [t for t in _failed_attempts[ip] if now - t < LOCKOUT_SECONDS]
    if len(_failed_attempts[ip]) >= MAX_ATTEMPTS:
        remaining = int(LOCKOUT_SECONDS - (now - _failed_attempts[ip][0]))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed attempts. Try again in {remaining} seconds."
        )

def _record_failure(ip: str):  _failed_attempts[ip].append(time.time())
def _clear_failures(ip: str):  _failed_attempts.pop(ip, None)

def _get_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ── SIGNUP — now sends verification email ─────────────────────────────────────
@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(
    user: UserCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    if len(user.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    db_user = db.query(User).filter(User.email == user.email.lower().strip()).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered. Please login instead."
        )

    # Generate secure verification token
    verification_token = secrets.token_urlsafe(32)

    new_user = User(
        email=user.email.lower().strip(),
        full_name=user.full_name.strip(),
        hashed_password=hash_password(user.password),
        career_track=user.career_track,
        country=user.country,
        is_hr=user.is_hr or False,
        company_name=user.company_name,
        is_verified=False,                  # not verified yet
        verification_token=verification_token,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Send verification email in background — non-blocking
    background_tasks.add_task(
        send_verification_email,
        to_email=new_user.email,
        token=verification_token,
        full_name=new_user.full_name or "",
    )

    # Return token immediately so user can still use the app
    # is_verified=False is just a soft gate — not blocking access
    token = create_access_token({"sub": new_user.email})
    return {"access_token": token, "token_type": "bearer"}


# ── GET /auth/verify-email?token=<token> ──────────────────────────────────────
@router.get("/verify-email")
def verify_email(
    token: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Called when user clicks the verification link in their email.
    Marks is_verified=True, clears the token, sends welcome email.
    """
    user = db.query(User).filter(User.verification_token == token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link.")
    if user.is_verified:
        return {"message": "Email already verified. You're good to go!"}

    user.is_verified        = True
    user.verification_token = None
    db.commit()

    # Send welcome email in background
    background_tasks.add_task(
        send_welcome_email,
        to_email=user.email,
        full_name=user.full_name or "",
    )

    return {"message": "Email verified successfully! Welcome to Baalebos Cloud."}


# ── POST /auth/resend-verification ────────────────────────────────────────────
@router.post("/resend-verification")
def resend_verification(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Resend verification email if user hasn't verified yet."""
    if current_user.is_verified:
        return {"message": "Your email is already verified."}

    token = secrets.token_urlsafe(32)
    current_user.verification_token = token
    db.commit()

    background_tasks.add_task(
        send_verification_email,
        to_email=current_user.email,
        token=token,
        full_name=current_user.full_name or "",
    )
    return {"message": "Verification email resent. Please check your inbox."}


# ── POST /auth/forgot-password ────────────────────────────────────────────────
@router.post("/forgot-password")
def forgot_password(
    email: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Send password reset link. Always returns 200 to prevent
    email enumeration attacks.
    """
    user = db.query(User).filter(User.email == email.lower().strip()).first()
    if user:
        reset_token = secrets.token_urlsafe(32)
        user.reset_token         = reset_token
        user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
        db.commit()

        background_tasks.add_task(
            send_password_reset_email,
            to_email=user.email,
            token=reset_token,
            full_name=user.full_name or "",
        )

    # Always return same response to prevent email enumeration
    return {"message": "If that email exists, a reset link has been sent."}


# ── POST /auth/reset-password ─────────────────────────────────────────────────
@router.post("/reset-password")
def reset_password(
    token: str,
    new_password: str,
    db: Session = Depends(get_db)
):
    """Validate reset token and update password."""
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    user = db.query(User).filter(User.reset_token == token).first()
    if not user or not user.reset_token_expires:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link.")
    if user.reset_token_expires < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Reset link has expired. Please request a new one.")

    user.hashed_password     = hash_password(new_password)
    user.reset_token         = None
    user.reset_token_expires = None
    db.commit()

    return {"message": "Password reset successfully. You can now login with your new password."}


# ── LOGIN ─────────────────────────────────────────────────────────────────────
@router.post("/login", response_model=TokenResponse)
def login(user: UserLogin, request: Request, db: Session = Depends(get_db)):
    ip = _get_ip(request)
    _check_brute_force(ip)

    db_user = db.query(User).filter(User.email == user.email.lower().strip()).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        _record_failure(ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    _clear_failures(ip)
    token = create_access_token({"sub": db_user.email})
    return {"access_token": token, "token_type": "bearer"}


# ── GET /auth/me ──────────────────────────────────────────────────────────────
@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


# ── POST /auth/admin/login ────────────────────────────────────────────────────
@router.post("/admin/login")
def admin_login(user: UserLogin, request: Request, db: Session = Depends(get_db)):
    ip = _get_ip(request)
    _check_brute_force(ip)

    db_user = db.query(User).filter(User.email == user.email.lower().strip()).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        _record_failure(ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not db_user.is_admin:
        _record_failure(ip)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied. Admin account required.")

    _clear_failures(ip)
    token = create_access_token({"sub": db_user.email})
    return {
        "access_token": token,
        "token_type":   "bearer",
        "is_admin":     True,
        "email":        db_user.email,
        "full_name":    db_user.full_name,
        "redirect":     "/admin/dashboard"
    }
