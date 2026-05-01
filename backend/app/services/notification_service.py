from smtplib import SMTP
import ssl
from backend.app.core.config import settings

SMTP_HOST = settings.MAIL_SERVER
SMTP_PORT = settings.MAIL_PORT
SMTP_USER = settings.MAIL_USERNAME
SMTP_PASSWORD = settings.MAIL_PASSWORD


def send_email_notification(to_email: str, subject: str, body: str):
    try:
        with SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(
                SMTP_USER,
                to_email,
                f"Subject: {subject}\n\n{body}"
            )
        print("Email sent successfully")

    except Exception as e:
        print("Email failed:", str(e))
