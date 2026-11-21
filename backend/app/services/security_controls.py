"""Owner security controls: blocked IPs, account status, sign-in bookkeeping,
new-country notices and security alert emails to the owner.

Alert emails are sent from a background thread so a sign-in never waits on
the email provider, and each alert is de-duplicated (one per subject per day).
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta
from html import escape

from fastapi import HTTPException

logger = logging.getLogger(__name__)
ATTACK_ALERT_THRESHOLDS = (5, 25)      # failed sign-ins from one IP within an hour


# ── Blocked IPs ──────────────────────────────────────────────────────────────

def active_block(db, ip: str | None):
    from backend.app.models.security import BlockedIP
    if not ip:
        return None
    block = db.query(BlockedIP).filter(BlockedIP.ip == ip).first()
    if block and block.expires_at and block.expires_at <= datetime.utcnow():
        return None
    return block


def ensure_ip_allowed(db, request, *, email: str | None = None, portal: str | None = None):
    from backend.app.core.client_ip import client_ip
    from backend.app.services import security_events
    ip = client_ip(request)
    if active_block(db, ip):
        security_events.record('login.blocked', request, email=email, portal=portal, details={'reason': 'ip_blocked'})
        raise HTTPException(403, 'Access from your network has been blocked. Contact support if this is a mistake.')


def blocked_ips(db) -> list[dict]:
    from backend.app.models.security import BlockedIP
    now = datetime.utcnow()
    rows = db.query(BlockedIP).order_by(BlockedIP.created_at.desc()).all()
    return [{'ip': b.ip, 'reason': b.reason, 'created_by': b.created_by, 'created_at': _iso(b.created_at),
             'expires_at': _iso(b.expires_at), 'active': not b.expires_at or b.expires_at > now} for b in rows]


def block_ip(db, ip: str, *, reason: str | None, hours: int | None, admin) -> dict:
    import ipaddress
    from backend.app.models.security import BlockedIP
    try:
        ip = str(ipaddress.ip_address(ip.strip()))
    except ValueError:
        raise HTTPException(400, 'Enter a valid IPv4 or IPv6 address.')
    if admin.last_login_ip and admin.last_login_ip == ip:
        raise HTTPException(400, 'That is the address you are signed in from; blocking it would lock you out.')
    block = db.query(BlockedIP).filter(BlockedIP.ip == ip).first() or BlockedIP(ip=ip)
    block.reason = (reason or '').strip()[:255] or None
    block.created_by = admin.email
    block.created_at = datetime.utcnow()
    block.expires_at = datetime.utcnow() + timedelta(hours=hours) if hours else None
    db.add(block)
    db.commit()
    return {'ip': ip, 'expires_at': _iso(block.expires_at)}


def unblock_ip(db, ip: str) -> bool:
    from backend.app.models.security import BlockedIP
    deleted = db.query(BlockedIP).filter(BlockedIP.ip == ip.strip()).delete()
    db.commit()
    return bool(deleted)


# ── Account status at sign-in ────────────────────────────────────────────────

def ensure_account_usable(user, request=None, portal: str | None = None):
    """Refuse suspended accounts and accounts that must reset their password."""
    from backend.app.services import security_events
    if user.suspended_at is not None:
        if request is not None:
            security_events.record('login.denied', request, user=user, portal=portal, details={'reason': 'suspended'})
        raise HTTPException(403, 'This account has been suspended. Contact support if you think this is a mistake.')
    if user.force_password_reset:
        if request is not None:
            security_events.record('login.denied', request, user=user, portal=portal,
                                   details={'reason': 'password_reset_required'})
        raise HTTPException(403, 'For your security, you must set a new password. '
                                 'Use the link we emailed you, or "Forgot password".')


def record_sign_in(db, request, user, portal: str | None):
    """Last sign-in details on the account, plus a new-country notice."""
    from backend.app.core.client_ip import client_ip
    from backend.app.core.geoip import locate
    from backend.app.models.security_event import SecurityEvent
    from backend.app.services import security_events
    ip = client_ip(request)
    where = locate(ip)
    country = where.get('country')
    location = ', '.join(p for p in (where.get('city'), country) if p) or None
    known = {c for (c,) in db.query(SecurityEvent.country).filter(
        SecurityEvent.user_id == user.id, SecurityEvent.event == 'login.success',
        SecurityEvent.country.isnot(None), SecurityEvent.country != 'Private network').distinct().all()}
    user.last_login_at, user.last_login_ip, user.last_login_location = datetime.utcnow(), ip, location
    db.commit()
    if country and country != 'Private network' and known and country not in known:
        security_events.record('login.new_country', request, user=user, portal=portal,
                               details={'previous_countries': sorted(known)[:10]})
        _notify_user_new_country(user.email, user.full_name or '', location or country, ip)
        if is_admin_account(user):
            owner_alert(db, f'admin-country:{user.id}:{country}',
                        f'Admin sign-in from a new country: {country}',
                        f'<p><b>{escape(user.email)}</b> signed in to an admin account from '
                        f'<b>{escape(location or country)}</b> (IP {escape(ip or "unknown")}).</p>'
                        '<p>If this was not expected, suspend the account and sign it out everywhere '
                        'from the Owner console.</p>')


def note_failed_sign_in(db, request, email: str | None):
    """Alert the owner when one IP crosses a failed-sign-in threshold in an hour."""
    from backend.app.core.client_ip import client_ip
    from backend.app.models.security_event import SecurityEvent
    from backend.app.services.security_events import FAILURE_EVENTS
    ip = client_ip(request)
    if not ip:
        return
    since = datetime.utcnow() - timedelta(hours=1)
    rows = db.query(SecurityEvent.email).filter(SecurityEvent.ip == ip, SecurityEvent.ts >= since,
                                                SecurityEvent.event.in_(FAILURE_EVENTS)).all()
    count = len(rows)
    for threshold in ATTACK_ALERT_THRESHOLDS:
        if count == threshold:
            accounts = len({e for (e,) in rows if e})
            owner_alert(db, f'attack:{ip}:{threshold}', f'Possible password attack: {count} failed sign-ins from {ip}',
                        f'<p>{count} failed sign-ins in the last hour from <b>{escape(ip)}</b> '
                        f'against {accounts} account(s).</p><p>Review it in Owner console → Security, '
                        'where you can block the IP.</p>')


def is_admin_account(user) -> bool:
    return bool(user and (user.role == 'super_admin' or user.is_admin))


# ── Alert delivery ───────────────────────────────────────────────────────────

def owner_alert(db, dedupe_key: str, subject: str, body_html: str):
    """Email the owner (ADMIN_EMAIL or verified admins), at most once a day per key."""
    from backend.app.core.kv_store import safe_call
    from backend.app.services import security_events
    key = f'alert:{dedupe_key}'
    if safe_call('exists', key, default=False):
        return
    safe_call('setex', key, 86400, '1')
    try:
        from backend.app.routes.hr_auth import admin_alert_recipients
        recipients = admin_alert_recipients(db)
    except Exception:
        recipients = []
    security_events.record('alert.sent', details={'subject': subject[:200], 'recipients': len(recipients)})
    if recipients:
        _send_async(recipients, f'🛡️ Baalebos security: {subject}', _wrap(subject, body_html))


def _notify_user_new_country(email: str, name: str, where: str, ip: str | None):
    body = (f'<p>Hi {escape(name or "there")},</p><p>Your Baalebos account was just signed in to from '
            f'<b>{escape(where)}</b> (IP {escape(ip or "unknown")}), a country we have not seen for your account.</p>'
            '<p>If this was you, no action is needed. If not, reset your password now and use '
            '"Sign out of all devices" in Settings.</p>')
    _send_async([email], 'New sign-in to your Baalebos account', _wrap('New sign-in location', body))


def _wrap(title: str, body: str) -> str:
    return (f'<html><body style="font-family:Inter,Arial,sans-serif;color:#0f172a;max-width:560px;margin:auto;">'
            f'<h2 style="font-size:18px;">{escape(title)}</h2>{body}'
            '<p style="color:#64748b;font-size:12px;margin-top:24px;">Baalebos Cloud security notice</p></body></html>')


def _send_async(recipients: list[str], subject: str, html: str):
    def run():
        from backend.app.utils.email import send_account_message
        for to in recipients:
            try:
                send_account_message(to, subject, html)
            except Exception as exc:
                logger.warning('security_email_failed error_type=%s', type(exc).__name__)
    threading.Thread(target=run, name='security-email', daemon=True).start()


def _iso(value):
    return value.isoformat() + 'Z' if value else None
