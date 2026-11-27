"""Password reset delivery.

Runs as a background task after the response is sent, so the outcome is
recorded as a security event ("Reset email sent" or "Reset email failed"):
the Owner console shows whether the email actually left, not only that a
reset was requested."""
from __future__ import annotations

from types import SimpleNamespace


def deliver_reset_link(user_id: int, email: str, token: str, full_name: str = '', hours: int = 1,
                       forced: bool = False) -> bool:
    from backend.app.services import security_events
    from backend.app.utils.email import send_password_reset_email
    try:
        sent = send_password_reset_email(to_email=email, token=token, full_name=full_name, hours=hours)
    except Exception:          # never let mail failure escape a background task silently
        sent = False
    security_events.record('password.reset_email_sent' if sent else 'password.reset_email_failed',
                           user=SimpleNamespace(id=user_id, email=email),
                           details={'forced_by_admin': forced} if forced else None)
    return sent
