# =============================================================================
# backend/app/utils/email.py
# Lark Suite SMTP over SSL (port 465)
# Aligned with existing email.py SMTP pattern
# =============================================================================
import smtplib
import ssl
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from backend.app.core.config import settings


def _send(to_email: str, subject: str, html_content: str) -> bool:
    """
    Core send function — Lark Suite SMTP SSL port 465.
    Reused by all email functions below.
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
    msg["To"]      = to_email
    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP_SSL(settings.SMTP_HOST, int(settings.SMTP_PORT)) as server:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAILS_FROM_EMAIL, to_email, msg.as_string())
        print(f"[Email] Sent '{subject}' to {to_email}")
        return True
    except Exception as e:
        print(f"[Email] Failed to send to {to_email}: {str(e)}")
        return False


def send_verification_email(to_email: str, token: str, full_name: str = "") -> bool:
    """
    Sends email verification link after signup.
    Link: settings.FRONTEND_URL/verify-email?token=<token>
    Backend handles: GET /api/v1/auth/verify-email?token=<token>
    """
    verification_link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    name    = full_name or to_email.split("@")[0]
    subject = "Confirm your email address — Baalebos Cloud"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family:'Inter',Arial,sans-serif;background-color:#f8fafc;padding:40px 20px;">
      <div style="max-width:600px;margin:0 auto;">

        <!-- Header -->
        <div style="background:#0f172a;border-radius:16px;padding:32px;text-align:center;margin-bottom:24px;">
          <h1 style="color:#10b981;font-size:22px;margin:0;letter-spacing:-0.5px;">BAALEBOS CLOUD</h1>
          <p style="color:#94a3b8;font-size:11px;margin:6px 0 0;letter-spacing:2px;text-transform:uppercase;">AI Talent Infrastructure</p>
        </div>

        <!-- Body -->
        <div style="background:#ffffff;border-radius:16px;padding:32px;border:1px solid #e2e8f0;">
          <h2 style="color:#0f172a;font-size:20px;font-weight:800;margin:0 0 12px;">Confirm your email ✅</h2>
          <p style="color:#475569;font-size:15px;line-height:1.6;margin:0 0 24px;">
            Hi <strong>{name}</strong>, welcome to Baalebos Cloud!<br/>
            Click the button below to verify your email address and activate your account.
          </p>

          <!-- CTA -->
          <div style="text-align:center;margin:32px 0;">
            <a href="{verification_link}"
              style="display:inline-block;background:#10b981;color:#ffffff;font-weight:800;
                     font-size:14px;padding:16px 36px;border-radius:12px;text-decoration:none;
                     letter-spacing:1px;text-transform:uppercase;">
              Verify My Email →
            </a>
          </div>

          <p style="color:#94a3b8;font-size:12px;text-align:center;margin:0 0 20px;">
            This link expires in <strong>24 hours</strong>.<br/>
            If you didn't create an account, you can safely ignore this email.
          </p>

          <!-- Fallback link -->
          <div style="background:#f8fafc;border-radius:12px;padding:16px;border:1px solid #e2e8f0;">
            <p style="color:#64748b;font-size:11px;margin:0 0 6px;font-weight:700;">
              If the button doesn't work, copy this link into your browser:
            </p>
            <a href="{verification_link}"
              style="color:#10b981;font-size:11px;word-break:break-all;">
              {verification_link}
            </a>
          </div>
        </div>

        <p style="text-align:center;color:#cbd5e1;font-size:11px;margin-top:24px;">
          © {datetime.now().year} Baalebos Cloud · Built for global engineers
        </p>
      </div>
    </body>
    </html>
    """
    return _send(to_email, subject, html_content)


def send_welcome_email(to_email: str, full_name: str = "") -> bool:
    """
    Sent after successful email verification.
    Gives the user onboarding steps and a CTA to the dashboard.
    """
    name    = full_name or to_email.split("@")[0]
    subject = "🎉 You're verified — Welcome to Baalebos Cloud!"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family:'Inter',Arial,sans-serif;background-color:#f8fafc;padding:40px 20px;">
      <div style="max-width:600px;margin:0 auto;">

        <div style="background:#0f172a;border-radius:16px;padding:32px;text-align:center;margin-bottom:24px;">
          <h1 style="color:#10b981;font-size:22px;margin:0;letter-spacing:-0.5px;">BAALEBOS CLOUD</h1>
          <p style="color:#94a3b8;font-size:11px;margin:6px 0 0;letter-spacing:2px;text-transform:uppercase;">AI Talent Infrastructure</p>
        </div>

        <div style="background:#ffffff;border-radius:16px;padding:32px;border:1px solid #e2e8f0;">
          <h2 style="color:#0f172a;font-size:20px;font-weight:800;margin:0 0 12px;">You're verified! 🚀</h2>
          <p style="color:#475569;font-size:15px;line-height:1.6;margin:0 0 24px;">
            Hi <strong>{name}</strong>, your account is now fully active.
            Here's how to get started:
          </p>

          <!-- Steps -->
          {''.join([_step(n, t, d) for n, t, d in [
              ('1', 'Upload your resume',        'Get an instant ATS score and AI-optimized PDF'),
              ('2', 'Browse 1,000+ global jobs', 'Filtered by your country and career track'),
              ('3', 'Track your applications',   'See ATS match scores for every role you apply to'),
              ('4', 'Refer friends and earn',    'Get $5–$12 for every friend who upgrades to Pro'),
          ]])}

          <div style="text-align:center;margin-top:32px;">
            <a href="{settings.FRONTEND_URL}"
              style="display:inline-block;background:#10b981;color:#ffffff;font-weight:800;
                     font-size:13px;padding:14px 28px;border-radius:12px;text-decoration:none;
                     letter-spacing:1px;text-transform:uppercase;">
              Go to My Dashboard →
            </a>
          </div>
        </div>

        <p style="text-align:center;color:#cbd5e1;font-size:11px;margin-top:24px;">
          © {datetime.now().year} Baalebos Cloud · Built for global engineers
        </p>
      </div>
    </body>
    </html>
    """
    return _send(to_email, subject, html_content)


def send_password_reset_email(to_email: str, token: str, full_name: str = "") -> bool:
    """
    Password reset email — link valid for 1 hour.
    Link: settings.FRONTEND_URL/reset-password?token=<token>
    """
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    name      = full_name or to_email.split("@")[0]
    subject   = "🔐 Reset your Baalebos Cloud password"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family:'Inter',Arial,sans-serif;background-color:#f8fafc;padding:40px 20px;">
      <div style="max-width:600px;margin:0 auto;">

        <div style="background:#0f172a;border-radius:16px;padding:32px;text-align:center;margin-bottom:24px;">
          <h1 style="color:#10b981;font-size:22px;margin:0;letter-spacing:-0.5px;">BAALEBOS CLOUD</h1>
          <p style="color:#94a3b8;font-size:11px;margin:6px 0 0;letter-spacing:2px;text-transform:uppercase;">AI Talent Infrastructure</p>
        </div>

        <div style="background:#ffffff;border-radius:16px;padding:32px;border:1px solid #e2e8f0;">
          <h2 style="color:#0f172a;font-size:20px;font-weight:800;margin:0 0 12px;">Password reset requested 🔐</h2>
          <p style="color:#475569;font-size:15px;line-height:1.6;margin:0 0 24px;">
            Hi <strong>{name}</strong>, we received a request to reset your password.<br/>
            Click the button below — this link expires in <strong>1 hour</strong>.
          </p>

          <div style="text-align:center;margin:32px 0;">
            <a href="{reset_url}"
              style="display:inline-block;background:#0f172a;color:#ffffff;font-weight:800;
                     font-size:14px;padding:16px 36px;border-radius:12px;text-decoration:none;
                     letter-spacing:1px;text-transform:uppercase;">
              Reset My Password →
            </a>
          </div>

          <p style="color:#94a3b8;font-size:12px;text-align:center;margin:0 0 20px;">
            If you didn't request this, ignore this email — your password won't change.
          </p>

          <div style="background:#f8fafc;border-radius:12px;padding:16px;border:1px solid #e2e8f0;">
            <p style="color:#64748b;font-size:11px;margin:0 0 6px;font-weight:700;">
              If the button doesn't work, copy this link:
            </p>
            <a href="{reset_url}" style="color:#10b981;font-size:11px;word-break:break-all;">
              {reset_url}
            </a>
          </div>
        </div>

        <p style="text-align:center;color:#cbd5e1;font-size:11px;margin-top:24px;">
          © {datetime.now().year} Baalebos Cloud · Built for global engineers
        </p>
      </div>
    </body>
    </html>
    """
    return _send(to_email, subject, html_content)


def _step(num: str, title: str, desc: str) -> str:
    """Reusable onboarding step block for welcome email."""
    return f"""
    <div style="display:flex;gap:12px;margin-bottom:16px;align-items:flex-start;">
      <div style="width:28px;height:28px;background:#10b981;border-radius:50%;
                  display:flex;align-items:center;justify-content:center;
                  color:white;font-weight:800;font-size:12px;flex-shrink:0;">{num}</div>
      <div>
        <p style="margin:0;color:#0f172a;font-size:14px;font-weight:700;">{title}</p>
        <p style="margin:2px 0 0;color:#64748b;font-size:13px;">{desc}</p>
      </div>
    </div>
    """
