import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from backend.app.core.config import settings


def _send(to_email: str, subject: str, html: str):
    if not settings.MAIL_USERNAME or not settings.MAIL_PASSWORD:
        print(f"[Email] Skipped (no credentials) — would send to {to_email}: {subject}")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Baalebos Cloud <{settings.MAIL_USERNAME}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP(settings.MAIL_SERVER, settings.MAIL_PORT) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
            server.sendmail(settings.MAIL_USERNAME, to_email, msg.as_string())
        print(f"[Email] Sent to {to_email}")
    except Exception as e:
        print(f"[Email] Failed: {e}")


def send_application_confirmation(to_email: str, full_name: str, job_title: str, company: str):
    subject = f"✅ Application Confirmed — {job_title} at {company}"
    html = f"""
    <div style="font-family:'Inter',Arial,sans-serif;max-width:600px;margin:0 auto;background:#f8fafc;padding:32px;">
      <div style="background:#0f172a;border-radius:16px;padding:32px;text-align:center;margin-bottom:24px;">
        <h1 style="color:#10b981;font-size:22px;margin:0;letter-spacing:-0.5px;">BAALEBOS CLOUD</h1>
        <p style="color:#94a3b8;font-size:11px;margin:6px 0 0;letter-spacing:2px;text-transform:uppercase;">AI Talent Infrastructure</p>
      </div>
      <div style="background:#ffffff;border-radius:16px;padding:32px;border:1px solid #e2e8f0;">
        <h2 style="color:#0f172a;font-size:20px;font-weight:800;margin:0 0 8px;">Application Submitted! 🎉</h2>
        <p style="color:#475569;font-size:15px;margin:0 0 24px;">Hi <strong>{full_name}</strong>, your application has been received.</p>
        <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:12px;padding:20px;margin-bottom:24px;">
          <p style="margin:0 0 6px;color:#64748b;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;">Applied For</p>
          <p style="margin:0;color:#0f172a;font-size:18px;font-weight:800;">{job_title}</p>
          <p style="margin:4px 0 0;color:#10b981;font-size:14px;font-weight:700;">{company}</p>
        </div>
        <p style="color:#64748b;font-size:14px;line-height:1.6;margin:0 0 24px;">
          Your application is now being tracked in your dashboard. You can view the job details,
          send a direct message to the HR team, and monitor your application status — all from one place.
        </p>
        <a href="https://baalebo.xyz" style="display:inline-block;background:#10b981;color:#ffffff;font-weight:800;font-size:13px;padding:14px 28px;border-radius:12px;text-decoration:none;letter-spacing:1px;text-transform:uppercase;">
          View My Dashboard →
        </a>
      </div>
      <p style="text-align:center;color:#cbd5e1;font-size:11px;margin-top:24px;">
        © {__import__('datetime').datetime.now().year} Baalebos Cloud · Built for global engineers
      </p>
    </div>
    """
    _send(to_email, subject, html)


def send_email_notification(to_email: str, subject: str, body: str):
    """Generic plain-text notification (used by resume tasks)."""
    html = f"<div style='font-family:Arial,sans-serif;padding:24px;'><p>{body}</p></div>"
    _send(to_email, subject, html)
