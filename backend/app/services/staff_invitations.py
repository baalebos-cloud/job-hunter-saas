"""Staff role invitations.

Assigning a staff role in Owner console -> Access control no longer grants it
on the spot: the person receives a single-use link (7 days) and the role starts
only when they accept it, signed in to the invited account. A mistyped or
unexpected assignment therefore never opens the console to anyone.
"""
from __future__ import annotations

import html
from datetime import datetime, timedelta

from backend.app.core.config import settings

INVITE_DAYS = 7


def mask_email(email: str) -> str:
    local, _, domain = (email or '').partition('@')
    return f'{local[:1]}{"*" * max(len(local) - 1, 2)}@{domain}' if domain else email


def pending_for(db, user_id: int):
    from backend.app.models.security import StaffInvitation
    return (db.query(StaffInvitation).filter(StaffInvitation.user_id == user_id, StaffInvitation.status == 'pending')
            .order_by(StaffInvitation.id.desc()).all())


def cancel_pending(db, user_id: int) -> int:
    rows = pending_for(db, user_id)
    for row in rows:
        row.status, row.responded_at = 'cancelled', datetime.utcnow()
    return len(rows)


def create(db, user, role: str, actor) -> tuple[object, str]:
    """Replace any pending invitation for this person with a new one. Returns (invitation, raw token)."""
    from backend.app.models.security import StaffInvitation
    from backend.app.services.auth_service import new_opaque_token
    cancel_pending(db, user.id)
    raw, digest = new_opaque_token()
    invite = StaffInvitation(user_id=user.id, role=role, token_hash=digest, invited_by=getattr(actor, 'id', None),
                             expires_at=datetime.utcnow() + timedelta(days=INVITE_DAYS))
    db.add(invite)
    db.flush()
    return invite, raw


def refresh_token(db, invite) -> str:
    from backend.app.services.auth_service import new_opaque_token
    raw, digest = new_opaque_token()
    invite.token_hash, invite.expires_at = digest, datetime.utcnow() + timedelta(days=INVITE_DAYS)
    return raw


def find(db, raw_token: str):
    from backend.app.models.security import StaffInvitation
    from backend.app.services.auth_service import hash_token
    return db.query(StaffInvitation).filter(StaffInvitation.token_hash == hash_token(raw_token or '')).first()


def state(invite) -> str:
    if invite.status == 'pending' and invite.expires_at < datetime.utcnow():
        return 'expired'
    return invite.status


def invite_link(raw: str) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/staff-invite?token={raw}"


def invitation_message(name: str | None, role: str, invited_by: str | None, raw: str) -> tuple[str, str]:
    from backend.app.services.role_emails import ROLE_GUIDE
    from backend.app.services.support import _layout
    guide = ROLE_GUIDE.get(role) or {'label': role, 'summary': 'A staff role on Baalebos.', 'can': []}
    first = html.escape(name.split()[0]) if name else 'there'
    by = html.escape(invited_by) if invited_by else 'The Baalebos owner'
    can = ''.join(f'<li style="margin:4px 0;">{html.escape(item)}</li>' for item in guide['can'])
    link = invite_link(raw)
    body = (f'<p style="color:#475569;font-size:14px;line-height:1.6;">Hi {first}, {by} has invited you to join '
            f'Baalebos as <strong>{html.escape(guide["label"])}</strong>.</p>'
            f'<p style="color:#475569;font-size:14px;line-height:1.6;">{html.escape(guide["summary"])}</p>'
            + (f'<p style="color:#0f172a;font-size:14px;font-weight:600;margin:16px 0 4px;">What you will be able to do</p>'
               f'<ul style="color:#475569;font-size:14px;line-height:1.5;padding-left:20px;margin:0;">{can}</ul>' if can else '')
            + f'<p style="color:#475569;font-size:14px;line-height:1.6;margin-top:16px;">Nothing changes on your account '
              f'until you accept. You will be asked to sign in, and to turn on two-step verification before the staff '
              f'pages open.</p>'
              f'<p style="margin:20px 0 0;"><a href="{link}" style="background:#059669;color:#fff;text-decoration:none;'
              f'font-weight:600;padding:11px 18px;border-radius:10px;display:inline-block;">Review and accept the invitation</a></p>'
              f'<p style="color:#94a3b8;font-size:12px;margin-top:18px;">This link works once and expires in {INVITE_DAYS} days. '
              f'If you were not expecting it, ignore this email or tell us at {html.escape(settings.SUPPORT_EMAIL)}.</p>')
    return f'You are invited to join Baalebos as {guide["label"]}', _layout(f'Invitation: {guide["label"]}', body)


def send(email: str, name: str | None, role: str, invited_by: str | None, raw: str) -> bool:
    """Background task. Never raises."""
    from backend.app.services.support import _deliver
    subject, body = invitation_message(name, role, invited_by, raw)
    return _deliver(email, subject, body, reply_to=settings.SUPPORT_EMAIL)
