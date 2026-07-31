# =============================================================================
# backend/app/utils/email.py
# Email verification utility — wraps notification_service._send()
# Provides: send_verification_email, send_welcome_email, send_password_reset_email
# =============================================================================
import secrets
from datetime import datetime
from backend.app.services.notification_service import _send


FRONTEND_URL = __import__('os').getenv("FRONTEND_URL", "https://baalebo.xyz")


def send_verification_email(to_email: str, token: str, full_name: str = ""):
    """
    Send email verification link after signup.
    Link points to: FRONTEND_URL/verify-email?token=<token>
    Backend handles: GET /api/v1/auth/verify-email?token=<token>
    """
    verify_url = f"{FRONTEND_URL}/verify-email?token={token}"
    name       = full_name or to_email.split("@")[0]
    subject    = "✉️ Verify your Baalebos Cloud account"
    html = f"""
    <div style="font-family:'Inter',Arial,sans-serif;max-width:600px;margin:0 auto;background:#f8fafc;padding:32px;">
      <div style="background:#0f172a;border-radius:16px;padding:32px;text-align:center;margin-bottom:24px;">
        <h1 style="color:#10b981;font-size:22px;margin:0;letter-spacing:-0.5px;">BAALEBOS CLOUD</h1>
        <p style="color:#94a3b8;font-size:11px;margin:6px 0 0;letter-spacing:2px;text-transform:uppercase;">AI Talent Infrastructure</p>
      </div>
      <div style="background:#ffffff;border-radius:16px;padding:32px;border:1px solid #e2e8f0;">
        <h2 style="color:#0f172a;font-size:20px;font-weight:800;margin:0 0 8px;">Confirm your email ✅</h2>
        <p style="color:#475569;font-size:15px;margin:0 0 24px;">
          Hi <strong>{name}</strong>, welcome to Baalebos Cloud!<br/>
          Click the button below to verify your email address and activate your account.
        </p>
        <div style="text-align:center;margin:32px 0;">
          <a href="{verify_url}"
            style="display:inline-block;background:#10b981;color:#ffffff;font-weight:800;font-size:14px;
                   padding:16px 36px;border-radius:12px;text-decoration:none;letter-spacing:1px;text-transform:uppercase;">
            Verify My Email →
          </a>
        </div>
        <p style="color:#94a3b8;font-size:12px;text-align:center;margin:0;">
          This link expires in <strong>24 hours</strong>.<br/>
          If you didn't create an account, you can safely ignore this email.
        </p>
        <div style="margin-top:24px;padding:16px;background:#f8fafc;border-radius:12px;border:1px solid #e2e8f0;">
          <p style="color:#64748b;font-size:11px;margin:0 0 4px;font-weight:700;">Or copy this link:</p>
          <p style="color:#10b981;font-size:11px;margin:0;word-break:break-all;">{verify_url}</p>
        </div>
      </div>
      <p style="text-align:center;color:#cbd5e1;font-size:11px;margin-top:24px;">
        © {datetime.now().year} Baalebos Cloud · Built for global engineers
      </p>
    </div>
    """
    _send(to_email, subject, html)


def send_welcome_email(to_email: str, full_name: str = ""):
    """
    Sent after successful email verification.
    Gives the user a warm welcome with next steps.
    """
    name    = full_name or to_email.split("@")[0]
    subject = "🎉 Welcome to Baalebos Cloud — You're all set!"
    html = f"""
    <div style="font-family:'Inter',Arial,sans-serif;max-width:600px;margin:0 auto;background:#f8fafc;padding:32px;">
      <div style="background:#0f172a;border-radius:16px;padding:32px;text-align:center;margin-bottom:24px;">
        <h1 style="color:#10b981;font-size:22px;margin:0;letter-spacing:-0.5px;">BAALEBOS CLOUD</h1>
        <p style="color:#94a3b8;font-size:11px;margin:6px 0 0;letter-spacing:2px;text-transform:uppercase;">AI Talent Infrastructure</p>
      </div>
      <div style="background:#ffffff;border-radius:16px;padding:32px;border:1px solid #e2e8f0;">
        <h2 style="color:#0f172a;font-size:20px;font-weight:800;margin:0 0 8px;">You're verified! 🚀</h2>
        <p style="color:#475569;font-size:15px;margin:0 0 24px;">
          Hi <strong>{name}</strong>, your account is now fully active.<br/>
          Here's how to get the most out of Baalebos Cloud:
        </p>
        <div style="space-y:12px;">
          {_step("1", "Upload your resume", "Get an instant ATS score and AI-optimized PDF")}
          {_step("2", "Browse 1,000+ global jobs", "Filtered by your country and career track")}
          {_step("3", "Track your applications", "See ATS match scores for every role you apply to")}
          {_step("4", "Refer friends & earn", "Get $5–$12 for every friend who upgrades to Pro")}
        </div>
        <div style="text-align:center;margin-top:32px;">
          <a href="{FRONTEND_URL}"
            style="display:inline-block;background:#10b981;color:#ffffff;font-weight:800;font-size:13px;
                   padding:14px 28px;border-radius:12px;text-decoration:none;letter-spacing:1px;text-transform:uppercase;">
            Go to My Dashboard →
          </a>
        </div>
      </div>
      <p style="text-align:center;color:#cbd5e1;font-size:11px;margin-top:24px;">
        © {datetime.now().year} Baalebos Cloud · Built for global engineers
      </p>
    </div>
    """
    _send(to_email, subject, html)


def send_password_reset_email(to_email: str, token: str, full_name: str = ""):
    """
    Password reset email — link valid for 1 hour.
    Link: FRONTEND_URL/reset-password?token=<token>
    """
    reset_url = f"{FRONTEND_URL}/reset-password?token={token}"
    name      = full_name or to_email.split("@")[0]
    subject   = "🔐 Reset your Baalebos Cloud password"
    html = f"""
    <div style="font-family:'Inter',Arial,sans-serif;max-width:600px;margin:0 auto;background:#f8fafc;padding:32px;">
      <div style="background:#0f172a;border-radius:16px;padding:32px;text-align:center;margin-bottom:24px;">
        <h1 style="color:#10b981;font-size:22px;margin:0;letter-spacing:-0.5px;">BAALEBOS CLOUD</h1>
        <p style="color:#94a3b8;font-size:11px;margin:6px 0 0;letter-spacing:2px;text-transform:uppercase;">AI Talent Infrastructure</p>
      </div>
      <div style="background:#ffffff;border-radius:16px;padding:32px;border:1px solid #e2e8f0;">
        <h2 style="color:#0f172a;font-size:20px;font-weight:800;margin:0 0 8px;">Password reset requested 🔐</h2>
        <p style="color:#475569;font-size:15px;margin:0 0 24px;">
          Hi <strong>{name}</strong>, we received a request to reset your password.<br/>
          Click the button below to set a new password. This link expires in <strong>1 hour</strong>.
        </p>
        <div style="text-align:center;margin:32px 0;">
          <a href="{reset_url}"
            style="display:inline-block;background:#0f172a;color:#ffffff;font-weight:800;font-size:14px;
                   padding:16px 36px;border-radius:12px;text-decoration:none;letter-spacing:1px;text-transform:uppercase;">
            Reset My Password →
          </a>
        </div>
        <p style="color:#94a3b8;font-size:12px;text-align:center;margin:0;">
          If you didn't request this, ignore this email — your password won't change.
        </p>
      </div>
      <p style="text-align:center;color:#cbd5e1;font-size:11px;margin-top:24px;">
        © {datetime.now().year} Baalebos Cloud · Built for global engineers
      </p>
    </div>
    """
    _send(to_email, subject, html)


def _step(num: str, title: str, desc: str) -> str:
    return f"""
    <div style="display:flex;gap:12px;margin-bottom:16px;align-items:flex-start;">
      <div style="width:28px;height:28px;background:#10b981;border-radius:50%;display:flex;align-items:center;
                  justify-content:center;color:white;font-weight:800;font-size:12px;flex-shrink:0;">{num}</div>
      <div>
        <p style="margin:0;color:#0f172a;font-size:14px;font-weight:700;">{title}</p>
        <p style="margin:2px 0 0;color:#64748b;font-size:13px;">{desc}</p>
      </div>
    </div>
    """
