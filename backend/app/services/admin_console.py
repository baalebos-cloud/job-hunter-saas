"""Read models for the Owner console: overview, posture, users and jobs."""
from __future__ import annotations

import os
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import func


def _iso(value):
    return value.isoformat() + 'Z' if value else None


def _pct(current: int, previous: int):
    return None if not previous else round((current - previous) * 100 / previous, 1)


def admins(db):
    from backend.app.models.user import User
    return db.query(User).filter((User.role == 'super_admin') | (User.is_admin == True)).all()  # noqa: E712


def posture(db) -> dict:
    """Security score out of 100 with the checks behind it."""
    from backend.app.core.config import settings
    from backend.app.core.geoip import available
    from backend.app.services.mfa import admin_2fa_required
    admin_list = [a for a in admins(db) if a.suspended_at is None]
    without_2fa = [a.email for a in admin_list if not a.totp_enabled_at]
    alerts = bool(getattr(settings, 'RESEND_API_KEY', None)) and bool(admin_list or settings.ADMIN_EMAIL)
    checks = [
        ('Sign-in rate limiting and lockout', True, 20, None),
        ('Two-step verification on every admin', not without_2fa, 25,
         f'{len(without_2fa)} of {len(admin_list)} admin(s) not enrolled' if without_2fa else None),
        ('Two-step verification required for the console', admin_2fa_required(), 15, 'ADMIN_2FA_REQUIRED is off'),
        ('Security alert emails', alerts, 15, 'Set RESEND_API_KEY and ADMIN_EMAIL on Railway'),
        ('Sign-in location lookup', available(), 10, 'Set MAXMIND_LICENSE_KEY on Railway'),
        ('Metrics endpoint protected', bool(os.getenv('METRICS_TOKEN')), 10, 'Set METRICS_TOKEN on Railway'),
        ('Duplicate and disposable sign-ups refused', True, 5, None),
    ]
    score = sum(weight for _, ok, weight, _ in checks if ok)
    return {'score': score, 'admins_without_2fa': without_2fa,
            'checks': [{'label': label, 'ok': ok, 'hint': None if ok else hint} for label, ok, _, hint in checks]}


def system_status(db) -> dict:
    from backend.app.core.metrics import window_summary
    from backend.app.database import pool_status
    from backend.app.services.job_automation import automation_status
    try:
        window = window_summary(15)
    except Exception:
        window = {}
    try:
        write = pool_status()['write']
        capacity = (write.get('size') or 0) + max(write.get('overflow') or 0, 0)
        pool = round(write['checked_out'] * 100 / capacity) if capacity else None
    except Exception:
        pool = None
    try:
        last = automation_status(db).get('last_scrape')
    except Exception:
        last = None
    requests = window.get('requests') or 0
    return {'p95_ms': window.get('p95_ms'), 'requests_15m': requests,
            'error_rate': round((window.get('server_errors') or 0) * 100 / requests, 2) if requests else 0,
            'db_pool_pct': pool,
            'last_scrape': {'status': last['status'], 'started_at': _iso(last['started_at']),
                            'finished_at': _iso(last['finished_at']), 'summary': last['summary']} if last else None,
            'grafana_url': os.getenv('GRAFANA_URL') or None}


def overview(db) -> dict:
    from backend.app.models.application import Application
    from backend.app.models.job import Job
    from backend.app.models.resume import Resume
    from backend.app.models.security_event import SecurityEvent
    from backend.app.models.subscription import Subscription
    from backend.app.models.user import User
    from backend.app.services import account_integrity, security_events
    now = datetime.utcnow()
    week, two_weeks, month = now - timedelta(days=7), now - timedelta(days=14), now - timedelta(days=30)
    today = datetime(now.year, now.month, now.day)

    users_total = db.query(User).count()
    apps_week = db.query(Application).filter(Application.created_at >= week).count()
    apps_prev = db.query(Application).filter(Application.created_at >= two_weeks, Application.created_at < week).count()
    live_jobs = db.query(Job).filter(Job.is_active == True).count()  # noqa: E712

    days = [(month + timedelta(days=i + 1)).date() for i in range(30)]
    signups = Counter(d.date() for (d,) in db.query(User.created_at).filter(User.created_at >= month) if d)
    applications = Counter(d.date() for (d,) in db.query(Application.created_at).filter(Application.created_at >= month) if d)

    summary = security_events.summary(db)
    pending = (db.query(User).filter(User.is_hr == True, User.hr_approved == False,  # noqa: E712
                                     User.hr_rejected_at.is_(None)).order_by(User.created_at.asc()).all())
    sec_posture = posture(db)
    duplicates = [g for g in account_integrity.duplicate_groups(db) if g['active_duplicates']]

    attention = []
    if summary['suspicious_ips']:
        attention.append({'kind': 'suspicious_ips', 'tab': 'security', 'level': 'risk',
                          'title': f"{len(summary['suspicious_ips'])} suspicious IP(s)",
                          'detail': f"{sum(s['failures'] for s in summary['suspicious_ips'])} failed sign-ins in 24 h"})
    if pending:
        attention.append({'kind': 'pending_employers', 'tab': 'employers', 'level': 'warn',
                          'title': f'{len(pending)} employer(s) awaiting approval',
                          'detail': f"Oldest since {pending[0].created_at:%d %b %Y}" if pending[0].created_at else ''})
    if duplicates:
        attention.append({'kind': 'duplicates', 'tab': 'users', 'level': 'warn',
                          'title': f'{len(duplicates)} suspected duplicate account group(s)',
                          'detail': f"{sum(g['active_duplicates'] for g in duplicates)} account(s) to review"})
    if sec_posture['admins_without_2fa']:
        attention.append({'kind': 'mfa', 'tab': 'security', 'level': 'info', 'title': 'Two-step verification off',
                          'detail': f"{len(sec_posture['admins_without_2fa'])} admin(s) not enrolled"})

    activity = (db.query(SecurityEvent).filter(SecurityEvent.event != 'admin.security_viewed')
                .order_by(SecurityEvent.id.desc()).limit(8).all())
    return {
        'kpis': {
            'users': users_total,
            'users_this_week': db.query(User).filter(User.created_at >= week).count(),
            'users_today': db.query(User).filter(User.created_at >= today).count(),
            'live_jobs': live_jobs,
            'jobs_today': db.query(Job).filter(Job.first_seen_at >= today).count(),
            'employer_jobs': db.query(Job).filter(Job.posted_by_hr == True, Job.is_active == True).count(),  # noqa: E712
            'applications': db.query(Application).count(),
            'applications_this_week': apps_week,
            'applications_change_pct': _pct(apps_week, apps_prev),
            'resumes': db.query(Resume).count(),
        },
        'growth': [{'date': d.isoformat(), 'signups': signups.get(d, 0), 'applications': applications.get(d, 0)}
                   for d in days],
        'mix': {
            'candidates': db.query(User).filter(User.is_hr == False, User.role.is_(None)).count(),  # noqa: E712
            'employers_approved': db.query(User).filter(User.is_hr == True, User.hr_approved == True).count(),  # noqa: E712
            'employers_pending': len(pending),
            'admins': len(admins(db)),
            'paid': db.query(Subscription).filter(Subscription.plan != 'free', Subscription.status == 'active').count(),
            'suspended': db.query(User).filter(User.suspended_at.isnot(None)).count(),
        },
        'attention': attention,
        'activity': [security_events._serialize(e) for e in activity],
        'posture': sec_posture,
        'system': system_status(db),
    }


# ── Users ────────────────────────────────────────────────────────────────────

def user_status(u) -> str:
    if u.suspended_at is not None:
        return 'suspended'
    if not u.is_verified:
        return 'unverified'
    if u.is_hr and u.hr_rejected_at:
        return 'rejected'
    if u.is_hr and not u.hr_approved:
        return 'awaiting_approval'
    return 'active'


def user_role(u) -> str:
    if u.role:
        return u.role
    if u.is_admin:
        return 'super_admin'
    return 'employer' if u.is_hr else 'candidate'


def _users_query(db, *, q=None, role=None, status=None):
    from backend.app.models.user import User
    query = db.query(User)
    if q:
        term = f'%{q.strip().lower()}%'
        query = query.filter(func.lower(User.email).like(term) | func.lower(func.coalesce(User.full_name, '')).like(term)
                             | func.lower(func.coalesce(User.company_name, '')).like(term))
    if role == 'candidate':
        query = query.filter(User.is_hr == False, User.role.is_(None), User.is_admin != True)  # noqa: E712
    elif role == 'employer':
        query = query.filter(User.is_hr == True)  # noqa: E712
    elif role == 'admin':
        query = query.filter(User.role.isnot(None) | (User.is_admin == True))  # noqa: E712
    if status == 'suspended':
        query = query.filter(User.suspended_at.isnot(None))
    elif status == 'unverified':
        query = query.filter(User.suspended_at.is_(None), User.is_verified != True)  # noqa: E712
    elif status == 'awaiting_approval':
        query = query.filter(User.suspended_at.is_(None), User.is_hr == True, User.hr_approved != True,  # noqa: E712
                             User.hr_rejected_at.is_(None))
    elif status == 'active':
        query = query.filter(User.suspended_at.is_(None), User.is_verified == True)  # noqa: E712
    elif status == 'no_2fa':
        query = query.filter(User.totp_enabled_at.is_(None))
    return query


def list_users(db, *, q=None, role=None, status=None, page: int = 1, page_size: int = 25) -> dict:
    from backend.app.models.application import Application
    from backend.app.models.subscription import Subscription
    from backend.app.models.user import User
    page_size = max(1, min(page_size, 100))
    page = max(1, page)
    query = _users_query(db, q=q, role=role, status=status)
    total = query.count()
    users = query.order_by(User.created_at.desc(), User.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    ids = [u.id for u in users]
    apps = dict(db.query(Application.user_id, func.count(Application.id)).filter(Application.user_id.in_(ids))
                .group_by(Application.user_id).all()) if ids else {}
    plans = dict(db.query(Subscription.user_id, Subscription.plan).filter(Subscription.user_id.in_(ids)).all()) if ids else {}
    return {'total': total, 'page': page, 'page_size': page_size, 'items': [{
        'id': u.id, 'email': u.email, 'full_name': u.full_name, 'company_name': u.company_name,
        'role': user_role(u), 'status': user_status(u), 'plan': plans.get(u.id) or ('free' if not u.is_hr else None),
        'mfa_enabled': bool(u.totp_enabled_at), 'force_password_reset': bool(u.force_password_reset),
        'suspended_reason': u.suspended_reason, 'last_login_at': _iso(u.last_login_at),
        'last_login_location': u.last_login_location, 'last_login_ip': u.last_login_ip,
        'created_at': _iso(u.created_at), 'applications': int(apps.get(u.id, 0)), 'country': u.country,
    } for u in users]}


def users_csv(db, *, q=None, role=None, status=None):
    from backend.app.models.user import User
    yield ['id', 'email', 'full_name', 'company', 'role', 'status', 'two_step', 'country', 'joined_utc',
           'last_sign_in_utc', 'last_sign_in_location']
    for u in _users_query(db, q=q, role=role, status=status).order_by(User.id.asc()).yield_per(500):
        yield [u.id, u.email, u.full_name or '', u.company_name or '', user_role(u), user_status(u),
               'on' if u.totp_enabled_at else 'off', u.country or '', _iso(u.created_at) or '',
               _iso(u.last_login_at) or '', u.last_login_location or '']


# ── Jobs ─────────────────────────────────────────────────────────────────────

def list_jobs(db, *, q=None, source=None, status='active', page: int = 1, page_size: int = 25) -> dict:
    from backend.app.models.application import Application
    from backend.app.models.job import Job
    page_size, page = max(1, min(page_size, 100)), max(1, page)
    query = db.query(Job)
    if q:
        term = f'%{q.strip().lower()}%'
        query = query.filter(func.lower(func.coalesce(Job.title, '')).like(term) |
                             func.lower(func.coalesce(Job.company, '')).like(term))
    if source == 'employer':
        query = query.filter(Job.posted_by_hr == True)  # noqa: E712
    elif source == 'scraped':
        query = query.filter(Job.posted_by_hr != True)  # noqa: E712
    if status == 'active':
        query = query.filter(Job.is_active == True)  # noqa: E712
    elif status == 'expired':
        query = query.filter(Job.is_active != True)  # noqa: E712
    total = query.count()
    jobs = (query.order_by(func.coalesce(Job.first_seen_at, Job.scraped_at).desc(), Job.id.desc())
            .offset((page - 1) * page_size).limit(page_size).all())
    ids = [j.id for j in jobs]
    counts = dict(db.query(Application.job_id, func.count(Application.id)).filter(Application.job_id.in_(ids))
                  .group_by(Application.job_id).all()) if ids else {}
    week = datetime.utcnow() - timedelta(days=7)
    return {'total': total, 'page': page, 'page_size': page_size,
            'stats': {'live': db.query(Job).filter(Job.is_active == True).count(),  # noqa: E712
                      'employer_posted': db.query(Job).filter(Job.posted_by_hr == True, Job.is_active == True).count(),  # noqa: E712
                      'applications_7d': db.query(Application).filter(Application.created_at >= week).count()},
            'items': [{'id': j.id, 'title': j.title, 'company': j.company, 'location': j.location, 'url': j.url,
                       'source': 'employer' if j.posted_by_hr else (j.source or 'scraped'), 'work_type': j.work_type,
                       'is_active': bool(j.is_active), 'posted_at': _iso(j.first_seen_at or j.scraped_at),
                       'applicants': int(counts.get(j.id, 0))} for j in jobs]}
