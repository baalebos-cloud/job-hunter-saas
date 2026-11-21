"""Duplicate-account prevention and employer risk checks.

Sign-up rejects an address whose *canonical* form already belongs to an
account, so ``J.Doe+jobs@Gmail.com`` cannot register next to
``jdoe@gmail.com``. Canonical form: lower-case, ``+tag`` removed, and for
Gmail the dots removed and ``googlemail.com`` folded into ``gmail.com``.
Disposable inbox providers are refused outright and sign-ups per IP are
capped. Accounts that still look related (same canonical email from before
this check existed, same phone number, several sign-ups from one IP) are
grouped for the admin to review, reject or dismiss.
"""
from __future__ import annotations

import os
import re
from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import urlparse

GMAIL_DOMAINS = {'gmail.com', 'googlemail.com'}
DISPOSABLE_DOMAINS = {
    '10minutemail.com', 'burnermail.io', 'dispostable.com', 'emailondeck.com', 'fakeinbox.com',
    'getnada.com', 'guerrillamail.com', 'guerrillamail.net', 'mailinator.com', 'maildrop.cc',
    'mailnesia.com', 'minuteinbox.com', 'mohmal.com', 'sharklasers.com', 'spamgourmet.com',
    'temp-mail.org', 'tempmail.com', 'tempmailo.com', 'throwaway.email', 'trashmail.com',
    'yopmail.com', 'mail.tm', 'tmpmail.org', 'moakt.com', 'emailfake.com',
}
FREE_EMAIL_DOMAINS = {
    'gmail.com', 'googlemail.com', 'yahoo.com', 'yahoo.co.uk', 'ymail.com', 'hotmail.com', 'outlook.com',
    'live.com', 'msn.com', 'icloud.com', 'me.com', 'aol.com', 'protonmail.com', 'proton.me', 'gmx.com',
    'zoho.com', 'mail.com', 'yandex.com', 'qq.com', '163.com',
}
SIGNUPS_PER_IP_PER_DAY = 5
SAME_IP_GROUP_MIN = 3          # accounts from one sign-up IP within a week


def canonical_email(email: str | None) -> str:
    email = (email or '').strip().lower()
    if '@' not in email:
        return email
    local, domain = email.rsplit('@', 1)
    local = local.split('+', 1)[0]
    if domain in GMAIL_DOMAINS:
        local, domain = local.replace('.', ''), 'gmail.com'
    return f'{local}@{domain}'


def email_domain(email: str | None) -> str:
    return (email or '').strip().lower().rsplit('@', 1)[-1]


def is_disposable(email: str) -> bool:
    extra = {d.strip().lower() for d in os.getenv('DISPOSABLE_EMAIL_DOMAINS', '').split(',') if d.strip()}
    return email_domain(email) in DISPOSABLE_DOMAINS | extra


def find_account(db, email: str):
    """The existing account an address collides with (exact or canonical), or None."""
    from sqlalchemy import func
    from backend.app.models.user import User
    canon = canonical_email(email)
    return (db.query(User).filter((User.email_canonical == canon) |
                                  (func.lower(User.email) == (email or '').strip().lower())).first())


def check_new_signup(db, request, email: str, portal: str) -> str:
    """Raise HTTPException for a duplicate, disposable or rate-limited sign-up.

    Returns the canonical email to store on the new account."""
    from fastapi import HTTPException
    from backend.app.core.client_ip import client_ip
    from backend.app.core.rate_limit import hit
    from backend.app.services import security_events
    from backend.app.services.security_controls import ensure_ip_allowed
    ensure_ip_allowed(db, request, email=email, portal=portal)
    if is_disposable(email):
        security_events.record('signup.rejected', request, email=email, portal=portal,
                               details={'reason': 'disposable_email'})
        raise HTTPException(400, 'Temporary or disposable email addresses are not accepted. '
                                 'Please use a permanent email address.')
    existing = find_account(db, email)
    if existing is not None:
        security_events.record('signup.rejected', request, email=email, portal=portal,
                               details={'reason': 'duplicate_account', 'existing_user_id': existing.id})
        raise HTTPException(409, 'An account already exists for this email address. '
                                 'Sign in, or use "Forgot password" to recover it.')
    allowed, _ = hit(f'signup:ip:{client_ip(request)}', SIGNUPS_PER_IP_PER_DAY, 86400)
    if not allowed:
        security_events.record('signup.rejected', request, email=email, portal=portal,
                               details={'reason': 'too_many_signups_from_ip'})
        raise HTTPException(429, 'Too many accounts have been created from this network today. '
                                 'Please try again tomorrow or contact support.')
    return canonical_email(email)


# ── Admin review of suspected duplicates ─────────────────────────────────────

def _phone_key(phone: str | None) -> str | None:
    digits = re.sub(r'\D', '', phone or '')
    return digits[-10:] if len(digits) >= 7 else None


def _account(u) -> dict:
    return {'id': u.id, 'email': u.email, 'full_name': u.full_name, 'created_at': _iso(u.created_at),
            'is_verified': bool(u.is_verified), 'is_hr': bool(u.is_hr), 'role': u.role,
            'suspended': u.suspended_at is not None, 'last_login_at': _iso(u.last_login_at),
            'signup_ip': u.signup_ip}


def _iso(value):
    return value.isoformat() + 'Z' if value else None


def duplicate_groups(db, include_dismissed: bool = False) -> list[dict]:
    """Groups of accounts that look like one person: same canonical email,
    same phone number, or 3+ sign-ups from one IP within 7 days."""
    from backend.app.models.security import DismissedDuplicate
    from backend.app.models.user import User
    users = db.query(User).order_by(User.created_at.asc(), User.id.asc()).all()
    buckets: dict[tuple[str, str], list] = defaultdict(list)
    for u in users:
        buckets[('same_email', u.email_canonical or canonical_email(u.email))].append(u)
        phone = _phone_key(u.phone)
        if phone:
            buckets[('same_phone', phone)].append(u)
        if u.signup_ip:
            buckets[('same_signup_ip', u.signup_ip)].append(u)
    dismissed = set() if include_dismissed else {k for (k,) in db.query(DismissedDuplicate.group_key).all()}
    groups = []
    for (reason, value), members in buckets.items():
        if reason == 'same_signup_ip':
            recent = [m for m in members if m.created_at and m.created_at >= datetime.utcnow() - timedelta(days=7)]
            if len(recent) < SAME_IP_GROUP_MIN:
                continue
            members = recent
        if len(members) < 2:
            continue
        key = f'{reason}:{value}'[:160]
        if key in dismissed:
            continue
        accounts = [_account(m) for m in members]
        accounts[0]['original'] = True          # oldest account is kept by default
        groups.append({'key': key, 'reason': reason, 'value': value, 'accounts': accounts,
                       'active_duplicates': sum(1 for a in accounts[1:] if not a['suspended'])})
    order = {'same_email': 0, 'same_phone': 1, 'same_signup_ip': 2}
    return sorted(groups, key=lambda g: (g['active_duplicates'] == 0, order[g['reason']], -len(g['accounts'])))


# ── Employer risk checks ─────────────────────────────────────────────────────

def _host(url: str | None) -> str:
    if not url:
        return ''
    parsed = urlparse(url if '://' in url else f'https://{url}')
    host = (parsed.hostname or '').lower()
    return host[4:] if host.startswith('www.') else host


def employer_checks(db, user, suspicious_ips: set[str] | None = None) -> list[dict]:
    """[{level: ok|warn|risk, label}] shown on each employer card."""
    from backend.app.models.security_event import SecurityEvent
    from backend.app.models.user import User
    checks = []
    add = lambda level, label: checks.append({'level': level, 'label': label})  # noqa: E731
    domain = email_domain(user.email)
    add('ok' if user.is_verified else 'warn', 'Email verified' if user.is_verified else 'Email not verified yet')
    if is_disposable(user.email):
        add('risk', 'Disposable email domain')
    elif domain in FREE_EMAIL_DOMAINS:
        add('risk', 'Free email domain')
    site = _host(user.company_url)
    if not site:
        add('warn', 'No company website given')
    elif site == domain or site.endswith('.' + domain) or domain.endswith('.' + site):
        add('ok', 'Email domain matches website')
    else:
        add('warn', f'Email domain ≠ website ({site})')
    add('ok' if user.linkedin_url else 'warn', 'LinkedIn page given' if user.linkedin_url else 'No LinkedIn page')
    same_domain = (db.query(User).filter(User.is_hr == True, User.id != user.id,  # noqa: E712
                                         User.email.ilike(f'%@{domain}')).count()) if domain not in FREE_EMAIL_DOMAINS else 0
    if same_domain:
        add('warn', f'{same_domain} other employer account(s) at @{domain}')
    canon = user.email_canonical or canonical_email(user.email)
    if db.query(User).filter(User.id != user.id, User.email_canonical == canon).count():
        add('risk', 'Duplicate of an existing account')
    signup = (db.query(SecurityEvent).filter(SecurityEvent.user_id == user.id, SecurityEvent.event == 'hr.signup')
              .order_by(SecurityEvent.id.desc()).first())
    ip = user.signup_ip or (signup.ip if signup else None)
    if ip and suspicious_ips is not None and ip in suspicious_ips:
        add('risk', 'Sign-up IP flagged as suspicious')
    if signup and signup.country and user.country and signup.country != 'Private network' \
            and signup.country.lower() != user.country.strip().lower():
        add('warn', f'Stated country ≠ sign-up location ({signup.country})')
    return checks


def employer_card(db, user, suspicious_ips: set[str] | None = None) -> dict:
    from backend.app.models.security_event import SecurityEvent
    signup = (db.query(SecurityEvent).filter(SecurityEvent.user_id == user.id, SecurityEvent.event == 'hr.signup')
              .order_by(SecurityEvent.id.desc()).first())
    location = ', '.join(p for p in (signup.city, signup.country) if p) if signup else None
    status = ('rejected' if user.hr_rejected_at else 'approved' if user.hr_approved else 'pending')
    checks = employer_checks(db, user, suspicious_ips)
    return {'id': user.id, 'full_name': user.full_name, 'email': user.email, 'company_name': user.company_name,
            'job_title': user.hr_job_title, 'company_url': user.company_url, 'linkedin_url': user.linkedin_url,
            'country': user.country, 'created_at': _iso(user.created_at), 'is_verified': bool(user.is_verified),
            'status': status, 'rejected_reason': user.hr_rejected_reason, 'suspended': user.suspended_at is not None,
            'signup_ip': user.signup_ip or (signup.ip if signup else None), 'signup_location': location,
            'checks': checks, 'risk': 'risk' if any(c['level'] == 'risk' for c in checks)
            else 'warn' if any(c['level'] == 'warn' for c in checks) else 'ok'}
