"""Duplicate-account prevention and employer risk checks.

Sign-up rejects an address whose *canonical* form already belongs to an
account, so ``J.Doe+jobs@Gmail.com`` cannot register next to
``jdoe@gmail.com``. Canonical form: lower-case, ``+tag`` removed, and for
Gmail the dots removed and ``googlemail.com`` folded into ``gmail.com``.
Disposable inbox providers are refused outright (a bundled list of ~10,000
throwaway domains, plus domains whose mail servers belong to one, plus domains
with no mail server at all). One new candidate account per network (IPv4
address or IPv6 /64) and per browser device every 30 days; trusted networks
(offices, schools) can be allow-listed by the owner. Free scans are shared by
accounts that came from the same network or device, so a second account does
not bring a second free allowance. Accounts that still look related (same canonical email from before
this check existed, same phone number, several sign-ups from one IP) are
grouped for the admin to review, reject or dismiss.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

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
ONE_ACCOUNT_DAYS = 30          # one new candidate account per network/device in this window
BLOCKLIST_FILE = Path(__file__).resolve().parents[1] / 'data' / 'disposable_email_domains.txt'
_DEVICE_ID = re.compile(r'^[A-Za-z0-9_-]{16,64}$')


@lru_cache(maxsize=1)
def _bundled_blocklist() -> frozenset:
    """github.com/disposable-email-domains/disposable-email-domains (CC0), bundled
    so sign-up never depends on a third-party service being up."""
    try:
        lines = BLOCKLIST_FILE.read_text(encoding='utf-8').splitlines()
    except OSError:
        logger.error('disposable_blocklist_missing')
        return frozenset()
    return frozenset(line.strip().lower() for line in lines if line.strip() and not line.startswith('#'))


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


def _domain_and_parents(domain: str) -> list[str]:
    parts = domain.split('.')
    return ['.'.join(parts[i:]) for i in range(len(parts) - 1)]


def _owner_blocked_domains(db) -> set[str]:
    if db is None:
        return set()
    try:
        from backend.app.models.security import SignupRule
        return {v for (v,) in db.query(SignupRule.value).filter(SignupRule.kind == 'blocked_domain')}
    except Exception:
        return set()


def is_disposable(email: str, db=None) -> bool:
    """True for a throwaway-inbox domain or any subdomain of one (x.yopmail.com)."""
    extra = {d.strip().lower() for d in os.getenv('DISPOSABLE_EMAIL_DOMAINS', '').split(',') if d.strip()}
    blocked = DISPOSABLE_DOMAINS | extra | _bundled_blocklist() | _owner_blocked_domains(db)
    return any(d in blocked for d in _domain_and_parents(email_domain(email)))


def _resolve(domain: str, record: str) -> list[str]:
    import dns.resolver
    resolver = dns.resolver.Resolver()
    resolver.lifetime = resolver.timeout = 3.0
    try:
        return [r.to_text() for r in resolver.resolve(domain, record)]
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
        return []


def mail_domain_problem(domain: str, resolve=_resolve) -> str | None:
    """'no_mail_server' when the domain cannot receive email, 'disposable_mail_server'
    when its mail servers belong to a throwaway provider, else None.

    DNS timeouts and resolver errors are not held against the user (fail open):
    a slow DNS server must not stop a real person from signing up."""
    if domain in GMAIL_DOMAINS or domain in FREE_EMAIL_DOMAINS:
        return None
    try:
        mx_hosts = [h.split()[-1].rstrip('.').lower() for h in resolve(domain, 'MX')]
        mx_hosts = [h for h in mx_hosts if h]          # "0 ." is a null MX: no mail accepted
        if not mx_hosts:
            return None if resolve(domain, 'A') and not _null_mx(domain, resolve) else 'no_mail_server'
    except Exception as exc:
        logger.warning('mx_check_skipped error_type=%s', type(exc).__name__)
        return None
    blocked = DISPOSABLE_DOMAINS | _bundled_blocklist()
    if any(parent in blocked for host in mx_hosts for parent in _domain_and_parents(host)):
        return 'disposable_mail_server'
    return None


def _null_mx(domain: str, resolve) -> bool:
    return any(h.split()[-1] == '.' for h in resolve(domain, 'MX'))


def _mx_check_enabled() -> bool:
    from backend.app.core.config import settings
    return settings.ENVIRONMENT != 'test' and os.getenv('EMAIL_MX_CHECK', 'true').lower() != 'false'


# ── One account per network / device ─────────────────────────────────────────

def network_key(ip: str | None) -> str | None:
    """IPv4 address, or the /64 an IPv6 address belongs to (one household or phone).
    None for private, loopback or unparseable addresses: local networks and
    test clients are never grouped."""
    try:
        addr = ipaddress.ip_address((ip or '').strip())
    except ValueError:
        return None
    if not addr.is_global:
        return None
    if addr.version == 6:
        return str(ipaddress.ip_network(f'{addr}/64', strict=False))
    return str(addr)


def device_hash(request) -> str | None:
    """Keyed hash of the browser's random device id (X-Device-Id); the raw id is never stored."""
    from backend.app.core.config import settings
    raw = (request.headers.get('x-device-id') or '').strip() if request is not None else ''
    if not _DEVICE_ID.match(raw):
        return None
    return hmac.new(settings.SECRET_KEY.encode(), raw.encode(), hashlib.sha256).hexdigest()


def is_trusted_network(db, ip: str | None) -> bool:
    try:
        addr = ipaddress.ip_address((ip or '').strip())
        from backend.app.models.security import SignupRule
        rules = [v for (v,) in db.query(SignupRule.value).filter(SignupRule.kind == 'allowed_network')]
    except Exception:
        return False
    for rule in rules:
        try:
            if addr in ipaddress.ip_network(rule, strict=False):
                return True
        except ValueError:
            continue
    return False


def signup_fingerprint(request) -> dict:
    """Columns stored on a new account: where it was created from."""
    from backend.app.core.client_ip import client_ip
    return {'signup_network': network_key(client_ip(request)), 'signup_device': device_hash(request)}


def recent_account_from(db, request):
    """An account created from this network or device in the last 30 days, or None."""
    from sqlalchemy import or_
    from backend.app.core.client_ip import client_ip
    from backend.app.models.user import User
    ip = client_ip(request)
    fp = signup_fingerprint(request)
    conditions = []
    if fp['signup_network'] and not is_trusted_network(db, ip):
        conditions += [User.signup_network == fp['signup_network'], User.signup_ip == ip]
    if fp['signup_device']:
        conditions.append(User.signup_device == fp['signup_device'])
    if not conditions:
        return None, None
    since = datetime.utcnow() - timedelta(days=ONE_ACCOUNT_DAYS)
    existing = (db.query(User).filter(or_(*conditions), User.created_at >= since, User.is_hr.isnot(True))
                .order_by(User.created_at.asc()).first())
    if existing is None:
        return None, None
    same_device = bool(fp['signup_device']) and existing.signup_device == fp['signup_device']
    return existing, 'device' if same_device else 'network'


def linked_accounts(db, user) -> list:
    """Other candidate accounts created from the same network or device (never trusted networks)."""
    from sqlalchemy import or_
    from backend.app.models.user import User
    conditions = []
    if user.signup_network and not is_trusted_network(db, user.signup_ip):
        conditions.append(User.signup_network == user.signup_network)
    if user.signup_device:
        conditions.append(User.signup_device == user.signup_device)
    if not conditions:
        return []
    return db.query(User).filter(or_(*conditions), User.id != user.id, User.is_hr.isnot(True)).all()


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
    from backend.app.core.config import settings
    from backend.app.core.rate_limit import hit
    from backend.app.services import security_events
    from backend.app.services.security_controls import ensure_ip_allowed
    ensure_ip_allowed(db, request, email=email, portal=portal)

    def refuse(status: int, reason: str, message: str, **details):
        security_events.record('signup.rejected', request, email=email, portal=portal,
                               details={'reason': reason, **details})
        raise HTTPException(status, message)

    disposable = 'Temporary or disposable email addresses are not accepted. Please use a permanent email address.'
    if is_disposable(email, db):
        refuse(400, 'disposable_email', disposable)
    if _mx_check_enabled():
        problem = mail_domain_problem(email_domain(email))
        if problem == 'disposable_mail_server':
            refuse(400, problem, disposable)
        if problem == 'no_mail_server':
            refuse(400, problem, 'This email domain cannot receive email. Check the address for typos, '
                                 'or use another email address.')
    existing = find_account(db, email)
    if existing is not None:
        refuse(409, 'duplicate_account', 'An account already exists for this email address. '
                                         'Sign in, or use "Forgot password" to recover it.', existing_user_id=existing.id)
    if portal == 'login':          # candidates: one new account per network/device per 30 days
        earlier, how = recent_account_from(db, request)
        if earlier is not None:
            refuse(409, f'duplicate_{how}', 'An account was already created from this '
                   f'{"device" if how == "device" else "network"} in the last {ONE_ACCOUNT_DAYS} days. '
                   'Sign in to that account instead, or use "Forgot password" to recover it. '
                   f'If several people share this network (an office or school), contact {settings.SUPPORT_EMAIL}.',
                   existing_user_id=earlier.id)
    allowed, _ = hit(f'signup:ip:{client_ip(request)}', SIGNUPS_PER_IP_PER_DAY, 86400)
    if not allowed:
        refuse(429, 'too_many_signups_from_ip', 'Too many accounts have been created from this network today. '
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
    if is_disposable(user.email, db):
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
