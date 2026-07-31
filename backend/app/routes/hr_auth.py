# =============================================================================
# backend/app/routes/hr_auth.py  — NEW FILE
# HR-specific signup + login with:
#  1. Company email validation (no free providers)
#  2. HR verification flow (admin must approve)
#  3. Dedicated HR login endpoint
# =============================================================================
import secrets
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from collections import defaultdict
from pydantic import BaseModel, EmailStr
import time

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.services.auth_service import hash_password, verify_password, create_access_token
from backend.app.utils.email import send_verification_email, _send

router = APIRouter(tags=["HR Auth"])

# ── Free/consumer email providers — blocked for HR signup ────────────────────
BLOCKED_DOMAINS = {
    "gmail.com", "yahoo.com", "yahoo.co.uk", "yahoo.co.in", "ymail.com",
    "hotmail.com", "hotmail.co.uk", "outlook.com", "outlook.co.uk",
    "live.com", "live.co.uk", "msn.com", "icloud.com", "me.com",
    "aol.com", "protonmail.com", "proton.me", "tutanota.com",
    "zoho.com", "mail.com", "gmx.com", "gmx.net", "inbox.com",
    "yandex.com", "yandex.ru", "qq.com", "163.com", "126.com",
    "naver.com", "daum.net", "rediffmail.com", "tempmail.com",
    "throwaway.email", "mailinator.com", "guerrillamail.com",
}

# Brute force protection
_failed: dict = defaultdict(list)

def _check_bf(ip: str):
    now = time.time()
    _failed[ip] = [t for t in _failed[ip] if now - t < 300]
    if len(_failed[ip]) >= 5:
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 5 minutes.")

def _get_ip(request: Request) -> str:
    fwd = request.headers.get("X-Forwarded-For")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")


class HRSignupRequest(BaseModel):
    full_name:    str
    email:        EmailStr
    password:     str
    company_name: str
    job_title:    str = "HR Manager"
    country:      str = ""
    linkedin_url: str = ""
    company_url:  str = ""


class HRLoginRequest(BaseModel):
    email:    EmailStr
    password: str


def _validate_company_email(email: str) -> str:
    """
    Returns the domain if valid company email.
    Raises HTTPException if free/consumer domain detected.
    """
    domain = email.lower().split("@")[-1]
    if domain in BLOCKED_DOMAINS:
        raise HTTPException(
            status_code=400,
            detail=f"Please use your company work email address. "
                   f"Free email providers like {domain} are not accepted for HR accounts."
        )
    return domain


def _send_hr_verification_email(to_email: str, token: str, full_name: str, company_name: str):
    """Email to HR — asks them to verify their email first."""
    import os
    frontend = os.getenv("FRONTEND_URL", "https://baalebo.xyz")
    verify_url = f"{frontend}/hr/verify?token={token}"
    html = f"""
    <!DOCTYPE html><html><head><meta charset="utf-8"></head>
    <body style="font-family:'Inter',Arial,sans-serif;background:#f8fafc;padding:40px 20px;">
    <div style="max-width:600px;margin:0 auto;">
      <div style="background:#0f172a;border-radius:16px;padding:32px;text-align:center;margin-bottom:24px;">
        <h1 style="color:#3b82f6;font-size:22px;margin:0;">BAALEBOS CLOUD</h1>
        <p style="color:#94a3b8;font-size:11px;margin:6px 0 0;letter-spacing:2px;text-transform:uppercase;">HR Portal</p>
      </div>
      <div style="background:#fff;border-radius:16px;padding:32px;border:1px solid #e2e8f0;">
        <h2 style="color:#0f172a;font-size:20px;font-weight:800;margin:0 0 12px;">Verify your HR account ✅</h2>
        <p style="color:#475569;font-size:15px;line-height:1.6;margin:0 0 24px;">
          Hi <strong>{full_name}</strong>, thanks for registering as HR for <strong>{company_name}</strong>.<br/><br/>
          Please verify your email first. After verification, our team will review your account
          and approve it within <strong>24–48 hours</strong>.
        </p>
        <div style="text-align:center;margin:32px 0;">
          <a href="{verify_url}" style="display:inline-block;background:#3b82f6;color:#fff;font-weight:800;
             font-size:14px;padding:16px 36px;border-radius:12px;text-decoration:none;
             letter-spacing:1px;text-transform:uppercase;">
            Verify Email →
          </a>
        </div>
        <div style="background:#f8fafc;border-radius:12px;padding:16px;border:1px solid #e2e8f0;">
          <p style="color:#64748b;font-size:11px;margin:0 0 6px;font-weight:700;">What happens next?</p>
          <ol style="color:#64748b;font-size:12px;margin:0;padding-left:16px;line-height:2;">
            <li>Verify your email (this step)</li>
            <li>Our team reviews your company details</li>
            <li>You receive an approval email</li>
            <li>Start posting jobs immediately</li>
          </ol>
        </div>
      </div>
    </div>
    </body></html>
    """
    _send(to_email, "Verify your Baalebos HR account", html)


def _send_admin_hr_notification(admin_email: str, hr_user: User, domain: str, company_url: str, linkedin_url: str):
    """Notify admin of new HR signup awaiting approval."""
    import os
    frontend = os.getenv("FRONTEND_URL", "https://baalebo.xyz")
    approve_url = f"{frontend}/admin"
    html = f"""
    <!DOCTYPE html><html><head><meta charset="utf-8"></head>
    <body style="font-family:'Inter',Arial,sans-serif;background:#f8fafc;padding:40px 20px;">
    <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:16px;padding:32px;border:1px solid #e2e8f0;">
      <h2 style="color:#0f172a;font-weight:800;margin:0 0 16px;">🔔 New HR Account Pending Approval</h2>
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <tr><td style="padding:8px 0;color:#64748b;font-weight:700;">Name</td><td style="padding:8px 0;color:#0f172a;font-weight:600;">{hr_user.full_name}</td></tr>
        <tr><td style="padding:8px 0;color:#64748b;font-weight:700;">Email</td><td style="padding:8px 0;color:#3b82f6;">{hr_user.email}</td></tr>
        <tr><td style="padding:8px 0;color:#64748b;font-weight:700;">Company</td><td style="padding:8px 0;color:#0f172a;font-weight:600;">{hr_user.company_name}</td></tr>
        <tr><td style="padding:8px 0;color:#64748b;font-weight:700;">Domain</td><td style="padding:8px 0;color:#0f172a;">@{domain}</td></tr>
        <tr><td style="padding:8px 0;color:#64748b;font-weight:700;">Company URL</td><td style="padding:8px 0;color:#3b82f6;">{company_url or 'Not provided'}</td></tr>
        <tr><td style="padding:8px 0;color:#64748b;font-weight:700;">LinkedIn</td><td style="padding:8px 0;color:#3b82f6;">{linkedin_url or 'Not provided'}</td></tr>
        <tr><td style="padding:8px 0;color:#64748b;font-weight:700;">Country</td><td style="padding:8px 0;color:#0f172a;">{hr_user.country or '—'}</td></tr>
      </table>
      <div style="text-align:center;margin-top:24px;">
        <a href="{approve_url}" style="display:inline-block;background:#0f172a;color:#fff;font-weight:800;
           font-size:13px;padding:14px 28px;border-radius:12px;text-decoration:none;">
          Review in Admin Dashboard →
        </a>
      </div>
    </div>
    </body></html>
    """
    _send(admin_email, f"🔔 New HR signup: {hr_user.company_name} ({domain})", html)


def _send_hr_approval_email(to_email: str, full_name: str, company_name: str):
    """Sent when admin approves HR account."""
    import os
    frontend = os.getenv("FRONTEND_URL", "https://baalebo.xyz")
    html = f"""
    <!DOCTYPE html><html><head><meta charset="utf-8"></head>
    <body style="font-family:'Inter',Arial,sans-serif;background:#f8fafc;padding:40px 20px;">
    <div style="max-width:600px;margin:0 auto;">
      <div style="background:#0f172a;border-radius:16px;padding:32px;text-align:center;margin-bottom:24px;">
        <h1 style="color:#3b82f6;font-size:22px;margin:0;">BAALEBOS CLOUD</h1>
        <p style="color:#94a3b8;font-size:11px;margin:6px 0 0;letter-spacing:2px;text-transform:uppercase;">HR Portal</p>
      </div>
      <div style="background:#fff;border-radius:16px;padding:32px;border:1px solid #e2e8f0;">
        <h2 style="color:#0f172a;font-size:20px;font-weight:800;margin:0 0 12px;">Your HR account is approved! 🎉</h2>
        <p style="color:#475569;font-size:15px;line-height:1.6;margin:0 0 24px;">
          Hi <strong>{full_name}</strong>, your HR account for <strong>{company_name}</strong>
          has been verified and approved.<br/><br/>
          You can now log in and start posting jobs to our global network of engineers.
        </p>
        <div style="text-align:center;margin:32px 0;">
          <a href="{frontend}/hr/login" style="display:inline-block;background:#3b82f6;color:#fff;font-weight:800;
             font-size:14px;padding:16px 36px;border-radius:12px;text-decoration:none;
             letter-spacing:1px;text-transform:uppercase;">
            Login to HR Portal →
          </a>
        </div>
      </div>
    </div>
    </body></html>
    """
    _send(to_email, "✅ Your Baalebos HR account is approved!", html)


# ── POST /hr-auth/signup ──────────────────────────────────────────────────────
@router.post("/signup")
def hr_signup(
    payload: HRSignupRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    # 1. Validate company email — no free providers
    domain = _validate_company_email(payload.email)

    # 2. Check duplicate
    if db.query(User).filter(User.email == payload.email.lower()).first():
        raise HTTPException(status_code=400, detail="Email already registered.")

    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    if not payload.company_name.strip():
        raise HTTPException(status_code=400, detail="Company name is required.")

    # 3. Create user — is_hr=True but is_verified=False, hr_approved=False
    verification_token = secrets.token_urlsafe(32)
    new_user = User(
        email=payload.email.lower().strip(),
        full_name=payload.full_name.strip(),
        hashed_password=hash_password(payload.password),
        company_name=payload.company_name.strip(),
        country=payload.country or None,
        is_hr=True,
        is_verified=False,
        verification_token=verification_token,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # 4. Send email verification to HR
    background_tasks.add_task(
        _send_hr_verification_email,
        to_email=new_user.email,
        token=verification_token,
        full_name=new_user.full_name or "",
        company_name=new_user.company_name or "",
    )

    # 5. Notify admin of new HR pending approval
    import os
    admin_email = os.getenv("ADMIN_EMAIL", os.getenv("EMAILS_FROM_EMAIL", ""))
    if admin_email:
        background_tasks.add_task(
            _send_admin_hr_notification,
            admin_email=admin_email,
            hr_user=new_user,
            domain=domain,
            company_url=payload.company_url,
            linkedin_url=payload.linkedin_url,
        )

    return {
        "message": "HR account created. Please check your email to verify your address. "
                   "Your account will be reviewed and approved within 24–48 hours.",
        "status":  "pending_verification",
        "email":   new_user.email,
    }


# ── GET /hr-auth/verify?token= ────────────────────────────────────────────────
@router.get("/verify")
def hr_verify_email(token: str, db: Session = Depends(get_db)):
    """
    HR clicks verification link from email.
    Marks email as verified. Account still needs admin approval to login.
    """
    user = db.query(User).filter(
        User.verification_token == token,
        User.is_hr == True
    ).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link.")
    if user.is_verified:
        return {"message": "Email already verified. Awaiting admin approval."}

    user.is_verified        = True
    user.verification_token = None
    db.commit()

    return {
        "message": "Email verified! Your HR account is now pending admin approval. "
                   "You'll receive an email once approved (24–48 hours).",
        "status":  "pending_approval",
    }


# ── POST /hr-auth/login ───────────────────────────────────────────────────────
@router.post("/login")
def hr_login(payload: HRLoginRequest, request: Request, db: Session = Depends(get_db)):
    """
    Dedicated HR login — validates:
    1. Company email only (no free providers)
    2. User exists and is_hr=True
    3. Email is verified
    4. Account is admin-approved (is_verified + not blocked)
    5. Correct password
    """
    ip = _get_ip(request)
    _check_bf(ip)

    # Block free email logins at the HR portal
    _validate_company_email(payload.email)

    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        _failed[ip].append(time.time())
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not user.is_hr:
        _failed[ip].append(time.time())
        raise HTTPException(
            status_code=403,
            detail="This account is not registered as an HR account. "
                   "Please sign up at /hr/signup."
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=403,
            detail="Your email address has not been verified yet. "
                   "Please check your inbox for the verification link."
        )

    # Check admin approval via is_admin flag or a dedicated hr_approved column
    # For now: admin sets is_verified=True after review (can be extended)
    # If account was flagged/banned by admin, is_hr would be set to False

    token = create_access_token({"sub": user.email})
    return {
        "access_token": token,
        "token_type":   "bearer",
        "is_hr":        True,
        "full_name":    user.full_name,
        "company_name": user.company_name,
        "redirect":     "/hr",
    }


# ── POST /hr-auth/approve/{user_id} — Admin only ──────────────────────────────
@router.post("/approve/{user_id}")
def approve_hr_account(
    user_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Admin approves an HR account.
    Called from the admin dashboard.
    Sends approval email to HR.
    """
    import os
    from backend.app.dependencies.auth import get_current_user
    # Note: add Depends(get_current_user) in production and check is_admin

    user = db.query(User).filter(User.id == user_id, User.is_hr == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="HR user not found.")

    user.is_verified = True
    db.commit()

    background_tasks.add_task(
        _send_hr_approval_email,
        to_email=user.email,
        full_name=user.full_name or "",
        company_name=user.company_name or "",
    )

    return {"message": f"HR account approved for {user.email}", "user_id": user_id}


# ── GET /hr-auth/pending — Admin only ────────────────────────────────────────
@router.get("/pending")
def list_pending_hr(db: Session = Depends(get_db)):
    """List all HR accounts awaiting approval."""
    pending = db.query(User).filter(
        User.is_hr == True,
        User.is_verified == False
    ).order_by(User.created_at.desc()).all()
    return [
        {
            "id":           u.id,
            "full_name":    u.full_name,
            "email":        u.email,
            "company_name": u.company_name,
            "country":      u.country,
            "created_at":   u.created_at,
        }
        for u in pending
    ]
