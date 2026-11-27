# =============================================================================
# backend/app/routes/auth.py — sign-up, sign-in, sessions, verification, reset
# =============================================================================
import re
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
    """Check the password and account status. The sign-in is recorded as a
    success only once it completes (see finish_login / the 2FA step)."""
    from backend.app.services import security_events, security_controls
    from backend.app.core.metrics import LOGIN_ATTEMPTS
    ip, email = client_ip(request), (email or '').lower().strip()
    security_controls.ensure_ip_allowed(db, request, email=email, portal=guard.scope)
    try:
        guard.check(ip, email)
    except HTTPException:
        security_events.record('login.blocked', request, email=email, portal=guard.scope)
        LOGIN_ATTEMPTS.labels(portal=guard.scope, outcome='blocked').inc()
        raise
    user = db.query(User).filter(User.email == email).first()
    ok, new_hash = verify_and_update_password(password, user.hashed_password) if user else (False, None)
    if not ok:
        guard.failure(ip, email)
        security_events.record('login.failed', request, user=user, email=email, portal=guard.scope,
                               details={'reason': 'wrong_password' if user else 'unknown_account'})
        LOGIN_ATTEMPTS.labels(portal=guard.scope, outcome='failed').inc()
        security_controls.note_failed_sign_in(db, request, email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if new_hash:  # transparently upgrade legacy bcrypt hashes
        user.hashed_password = new_hash
        db.commit()
    guard.success(ip, email)
    try:
        security_controls.ensure_account_usable(user, request, guard.scope)
    except HTTPException:
        LOGIN_ATTEMPTS.labels(portal=guard.scope, outcome='denied').inc()
        raise
    return user


def complete_login(db: Session, request: Request, user: User, portal: str):
    from backend.app.services import security_events, security_controls
    from backend.app.core.metrics import LOGIN_ATTEMPTS
    security_controls.record_sign_in(db, request, user, portal)
    security_events.record('login.success', request, user=user, portal=portal)
    LOGIN_ATTEMPTS.labels(portal=portal, outcome='success').inc()


def finish_login(db: Session, request: Request, response: Response, user: User, portal: str,
                 extra: dict | None = None) -> dict:
    """Start a session, or ask for the authenticator code when 2FA is on."""
    if user.totp_enabled_at:
        from backend.app.services.mfa import issue_mfa_token
        return {"mfa_required": True, "mfa_token": issue_mfa_token(user, {**(extra or {}), "portal": portal}),
                "token_type": "mfa"}
    complete_login(db, request, user, portal)
    return start_session(db, user, response, extra)


# ── SIGNUP ───────────────────────────────────────────────────────────────────
VERIFY_FIRST = ("Your email address has not been verified yet. Open the verification link we emailed you, "
                "or request a new one below.")
RESEND_MESSAGE = "If that account needs verifying, a new verification link is on its way. Check your inbox and spam folder."


def _attribute_referral(db: Session, new_user: User, ref_code: str | None):
    """Record who invited this account. Done server-side at signup because the
    account has no session until its email is verified. Never blocks signup."""
    if not ref_code:
        return
    from backend.app.models.referral import Referral
    try:
        referrer = db.query(User).filter(User.referral_code == ref_code.strip()[:64]).first()
        if not referrer or referrer.id == new_user.id:
            return
        if db.query(Referral).filter(Referral.referred_email == new_user.email).first():
            return
        db.add(Referral(referrer_id=referrer.id, referred_email=new_user.email,
                        referred_user_id=new_user.id, status='pending'))
        db.commit()
    except Exception:
        db.rollback()


_TAG = re.compile(r'[^a-z0-9_.\- ]+')


def _attribution(user) -> dict:
    """Campaign tags from the link that first brought the visitor, cleaned to
    short lowercase labels. The referrer is kept as a host name only."""
    def tag(value, limit):
        cleaned = _TAG.sub('', str(value or '').strip().lower())[:limit].strip()
        return cleaned or None
    referrer = str(user.referrer or '').strip().lower()
    host = re.sub(r'^[a-z]+://', '', referrer).split('/')[0].split(':')[0].removeprefix('www.')[:120]
    return {'signup_utm_source': tag(user.utm_source, 80), 'signup_utm_medium': tag(user.utm_medium, 80),
            'signup_utm_campaign': tag(user.utm_campaign, 120),
            'signup_referrer': host if re.fullmatch(r'[a-z0-9.\-]+\.[a-z]{2,}', host or '') else None}


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(user: UserCreate, request: Request, response: Response, background_tasks: BackgroundTasks,
           db: Session = Depends(get_db)):
    """Create the account and email a verification link. No session is started:
    the account can sign in only after the email address is verified."""
    if len(user.password) < MIN_PASSWORD:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    from backend.app.services.account_integrity import check_new_signup, signup_fingerprint
    canonical = check_new_signup(db, request, user.email, 'login')
    raw_token, token_digest = new_opaque_token()
    new_user = User(email=user.email.lower().strip(), full_name=user.full_name.strip(),
                    email_canonical=canonical, signup_ip=client_ip(request), **signup_fingerprint(request),
                    hashed_password=hash_password(user.password), career_track=user.career_track,
                    country=user.country, is_hr=False, company_name=user.company_name,
                    is_verified=False, verification_token=token_digest, **_attribution(user))
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    from backend.app.services import security_events
    security_events.record('signup', request, user=new_user, portal='login')
    _attribute_referral(db, new_user, user.ref_code)
    background_tasks.add_task(send_verification_email, to_email=new_user.email, token=raw_token,
                              full_name=new_user.full_name or "")
    return {"verification_required": True, "email": new_user.email,
            "message": "Account created. We emailed you a verification link: verify your email, then sign in."}


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


class ResendVerificationRequest(BaseModel):
    email: EmailStr


@router.post("/verification/resend")
def resend_verification_by_email(payload: ResendVerificationRequest, request: Request, background_tasks: BackgroundTasks,
                                 db: Session = Depends(get_db)):
    """For accounts that cannot sign in yet. Same answer whether or not the
    account exists (no enumeration); rate limited per email and per IP."""
    from backend.app.core.rate_limit import _email_key, hit
    email = payload.email.lower().strip()
    for key, limit in ((f'verify-resend:email:{_email_key(email)}', 3), (f'verify-resend:ip:{client_ip(request)}', 10)):
        allowed, retry_after = hit(key, limit, 3600)
        if not allowed:
            raise HTTPException(429, f'Too many requests. Try again in {retry_after // 60 + 1} minutes.',
                                headers={'Retry-After': str(retry_after)})
    user = db.query(User).filter(User.email == email, User.is_hr != True).first()  # noqa: E712
    if user and not user.is_verified:
        raw_token, token_digest = new_opaque_token()
        user.verification_token = token_digest      # the previous link stops working
        db.commit()
        background_tasks.add_task(send_verification_email, to_email=user.email, token=raw_token,
                                  full_name=user.full_name or "")
    return {"message": RESEND_MESSAGE}


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
def forgot_password(payload: ForgotPasswordRequest, request: Request, background_tasks: BackgroundTasks,
                    db: Session = Depends(get_db)):
    """Always returns the same response to prevent email enumeration."""
    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if user:
        from backend.app.services import security_events
        security_events.record('password.reset_requested', request, user=user)
        raw_token, token_digest = new_opaque_token()
        user.reset_token = token_digest
        user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
        db.commit()
        background_tasks.add_task(send_password_reset_email, to_email=user.email, token=raw_token,
                                  full_name=user.full_name or "")
    return {"message": "If that email exists, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.reset_token == hash_token(payload.token)).first()
    if not user or not user.reset_token_expires:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link.")
    if user.reset_token_expires < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Reset link has expired. Please request a new one.")
    user.hashed_password = hash_password(payload.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    user.force_password_reset = False
    revoke_all_sessions(db, user)  # every existing JWT and refresh token stops working
    db.commit()
    from backend.app.services import security_events
    security_events.record('password.reset_completed', request, user=user)
    clear_refresh_cookie(response)
    return {"message": "Password reset successfully. You can now login with your new password."}


# ── LOGIN / SESSIONS ─────────────────────────────────────────────────────────
@router.post("/login", response_model=TokenResponse, response_model_exclude_none=True)
def login(user: UserLogin, request: Request, response: Response, db: Session = Depends(get_db)):
    account = authenticate(db, request, user.email, user.password)
    if not account.is_verified:
        # Checked after the password, so it never reveals whether an email is registered.
        from backend.app.services import security_events
        security_events.record('login.denied', request, user=account, portal='login', details={'reason': 'email_unverified'})
        raise HTTPException(403, {'code': 'email_not_verified', 'message': VERIFY_FIRST, 'email': account.email})
    return finish_login(db, request, response, account, 'login')


class MfaLoginRequest(BaseModel):
    mfa_token: str = Field(min_length=20, max_length=4096)
    code: str = Field(min_length=6, max_length=32)


@router.post("/login/mfa")
def login_mfa(payload: MfaLoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    """Second sign-in step: the 6-digit authenticator code or a recovery code."""
    from backend.app.core.kv_store import safe_call
    from backend.app.core.rate_limit import _email_key, hit
    from backend.app.services import mfa, security_controls, security_events
    claims = mfa.read_mfa_token(payload.mfa_token)
    if not claims or safe_call('exists', f"mfa:spent:{claims['jti']}", default=False):
        raise HTTPException(401, "This sign-in step has expired. Please sign in again.")
    allowed, retry = hit(f"mfa:{_email_key(claims['sub'])}", 5, 300)
    if not allowed:
        raise HTTPException(429, f"Too many codes tried. Wait {retry} seconds and sign in again.",
                            headers={"Retry-After": str(retry)})
    user = db.query(User).filter(User.email == claims['sub']).first()
    if not user or not user.totp_enabled_at or int(claims.get('tv', 0)) != int(user.token_version or 0):
        raise HTTPException(401, "This sign-in step has expired. Please sign in again.")
    extra = dict(claims.get('x') or {})
    portal = extra.pop('portal', 'login')
    security_controls.ensure_account_usable(user, request, portal)
    code = payload.code.strip()
    used_recovery = False
    if not mfa.verify_code(user, code):
        used_recovery = mfa.use_recovery_code(user, code)
        if not used_recovery:
            security_events.record('login.failed', request, user=user, portal=portal,
                                   details={'reason': 'wrong_2fa_code'})
            security_controls.note_failed_sign_in(db, request, user.email)
            raise HTTPException(401, "That code is not valid. Check your authenticator app and try again.")
        db.commit()
    safe_call('setex', f"mfa:spent:{claims['jti']}", mfa.MFA_TOKEN_MINUTES * 60, '1')
    complete_login(db, request, user, portal)
    if used_recovery:
        extra['recovery_codes_left'] = len(user.totp_recovery_codes or [])
    return start_session(db, user, response, extra)


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
    if not user.is_verified:
        # Sessions opened before verification was required end here.
        from fastapi.responses import JSONResponse
        denied = JSONResponse({"detail": {'code': 'email_not_verified', 'message': VERIFY_FIRST}}, status_code=401)
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
            "role": current_user.role, "permissions": permissions,
            "mfa_enabled": bool(current_user.totp_enabled_at), "photo_url": current_user.photo_url}


# ── ADMIN LOGIN ──────────────────────────────────────────────────────────────
@router.post("/admin/login")
def admin_login(user: UserLogin, request: Request, response: Response, db: Session = Depends(get_db)):
    from backend.app.dependencies.roles import has_permission
    db_user = authenticate(db, request, user.email, user.password, LoginGuard('admin'))
    if not has_permission(db, db_user, 'admin:access'):
        LoginGuard('admin').failure(client_ip(request), user.email)
        from backend.app.services import security_events
        security_events.record('login.denied', request, user=db_user, portal='admin',
                               details={'reason': 'not_an_admin'})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied. Admin account required.")
    return finish_login(db, request, response, db_user, 'admin',
                        {"is_admin": True, "email": db_user.email, "full_name": db_user.full_name, "redirect": "/admin"})


# ── TWO-STEP VERIFICATION (authenticator app) ────────────────────────────────
class MfaCode(BaseModel):
    code: str = Field(min_length=6, max_length=32)


@router.get("/2fa")
def mfa_status(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from backend.app.dependencies.roles import has_permission
    from backend.app.services.mfa import admin_2fa_required
    return {"enabled": bool(current_user.totp_enabled_at),
            "enabled_at": current_user.totp_enabled_at.isoformat() + "Z" if current_user.totp_enabled_at else None,
            "recovery_codes_left": len(current_user.totp_recovery_codes or []),
            "required": admin_2fa_required() and has_permission(db, current_user, 'admin:access')}


@router.post("/2fa/setup")
def mfa_setup(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a new secret (not active until confirmed with a code)."""
    from backend.app.services import mfa
    if current_user.totp_enabled_at:
        raise HTTPException(400, "Two-step verification is already on. Turn it off first to change devices.")
    secret = mfa.new_secret()
    current_user.totp_secret = mfa.encrypt_secret(secret)
    db.commit()
    return {"secret": secret, "otpauth_uri": mfa.otpauth_uri(secret, current_user.email)}


@router.post("/2fa/enable")
def mfa_enable(payload: MfaCode, request: Request, response: Response,
               current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Confirm the first code. Other sessions are signed out; this one continues."""
    from backend.app.services import mfa, security_events
    if current_user.totp_enabled_at:
        raise HTTPException(400, "Two-step verification is already on.")
    if not current_user.totp_secret or not mfa.verify_code(current_user, payload.code):
        raise HTTPException(400, "That code is not valid. Check the time on your phone and try the newest code.")
    current_user.totp_enabled_at = datetime.utcnow()
    codes = mfa.new_recovery_codes(current_user)
    revoke_all_sessions(db, current_user)
    db.commit()
    security_events.record('mfa.enabled', request, user=current_user)
    return start_session(db, current_user, response, {"recovery_codes": codes})


@router.post("/2fa/disable")
def mfa_disable(payload: MfaCode, request: Request, current_user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    from backend.app.services import mfa, security_controls, security_events
    if not current_user.totp_enabled_at:
        return {"message": "Two-step verification is already off."}
    if not (mfa.verify_code(current_user, payload.code) or mfa.use_recovery_code(current_user, payload.code)):
        raise HTTPException(400, "That code is not valid.")
    current_user.totp_secret = None
    current_user.totp_enabled_at = None
    current_user.totp_recovery_codes = None
    db.commit()
    security_events.record('mfa.disabled', request, user=current_user)
    if security_controls.is_admin_account(current_user):
        from html import escape
        security_controls.owner_alert(db, f'mfa-off:{current_user.id}:{datetime.utcnow():%Y%m%d%H%M}',
                                      'Two-step verification turned off on an admin account',
                                      f'<p><b>{escape(current_user.email)}</b> turned off two-step verification.</p>')
    return {"message": "Two-step verification is off."}


@router.post("/2fa/recovery-codes")
def mfa_new_recovery_codes(payload: MfaCode, request: Request, current_user: User = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    from backend.app.services import mfa, security_events
    if not current_user.totp_enabled_at or not mfa.verify_code(current_user, payload.code):
        raise HTTPException(400, "That code is not valid.")
    codes = mfa.new_recovery_codes(current_user)
    db.commit()
    security_events.record('mfa.recovery_codes_reset', request, user=current_user)
    return {"recovery_codes": codes}
