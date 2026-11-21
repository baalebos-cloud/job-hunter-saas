"""Record and query security events (see models/security_event.py).

Recording never breaks the request it observes: failures are logged and
dropped. Writes use their own short session so a rolled-back request still
leaves its security trail (e.g. a failed sign-in).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

EVENTS = {
    'login.success': 'Signed in',
    'login.failed': 'Failed sign-in',
    'login.blocked': 'Sign-in blocked (too many attempts)',
    'login.denied': 'Signed in without access to this portal',
    'signup': 'Candidate sign-up',
    'hr.signup': 'Employer sign-up',
    'password.reset_requested': 'Password reset requested',
    'password.reset_completed': 'Password reset completed',
    'admin.hr_approved': 'Admin approved an employer',
    'admin.made_hr': 'Admin made a user an employer',
    'admin.made_admin': 'Admin granted admin rights',
    'admin.role_changed': 'Admin changed a governance role',
    'admin.user_deleted': 'Admin deleted a user',
    'admin.job_deleted': 'Admin deleted a job',
    'admin.security_viewed': 'Admin viewed security events',
}
FAILURE_EVENTS = ('login.failed', 'login.blocked', 'login.denied')
SUSPICIOUS_FAILURES = 5          # failed sign-ins from one IP within the window


def _session():
    from backend.app import database
    return database.SessionLocal()


def record(event: str, request=None, *, user=None, email: str | None = None, portal: str | None = None,
           details: dict | None = None) -> None:
    from backend.app.core.client_ip import client_ip
    from backend.app.core.geoip import locate
    from backend.app.models.security_event import SecurityEvent
    try:
        ip = client_ip(request) if request is not None else None
        agent = (request.headers.get('user-agent') or '')[:255] if request is not None else None
        row = SecurityEvent(ts=datetime.utcnow(), event=event[:40], portal=portal,
                            user_id=getattr(user, 'id', None),
                            email=(email or getattr(user, 'email', None) or '').strip().lower()[:255] or None,
                            ip=(ip or None) and ip[:64], user_agent=agent or None, details=details or None,
                            **locate(ip))
        db = _session()
        try:
            db.add(row)
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        logger.error('security_event_write_failed event=%s error_type=%s', event, type(exc).__name__)
        return
    try:
        from backend.app.core.metrics import SECURITY_EVENTS
        SECURITY_EVENTS.labels(event=event).inc()
    except Exception:
        pass


def _serialize(e) -> dict:
    location = ', '.join(p for p in (e.city, e.region, e.country) if p) or None
    return {'id': e.id, 'ts': e.ts.isoformat() + 'Z', 'event': e.event, 'label': EVENTS.get(e.event, e.event),
            'portal': e.portal, 'user_id': e.user_id, 'email': e.email, 'ip': e.ip,
            'country_code': e.country_code, 'location': location, 'user_agent': e.user_agent,
            'details': e.details}


def list_events(db, *, event: str | None = None, q: str | None = None, ip: str | None = None,
                limit: int = 100, before_id: int | None = None) -> list[dict]:
    from backend.app.models.security_event import SecurityEvent
    query = db.query(SecurityEvent)
    if event:
        query = query.filter(SecurityEvent.event == event)
    if ip:
        query = query.filter(SecurityEvent.ip == ip.strip())
    if q:
        term = f'%{q.strip().lower()}%'
        query = query.filter(SecurityEvent.email.ilike(term) | SecurityEvent.ip.ilike(term) |
                             SecurityEvent.country.ilike(term) | SecurityEvent.city.ilike(term))
    if before_id:
        query = query.filter(SecurityEvent.id < before_id)
    return [_serialize(e) for e in query.order_by(SecurityEvent.id.desc()).limit(max(1, min(limit, 500)))]


def summary(db, now: datetime | None = None) -> dict:
    from sqlalchemy import func
    from backend.app.core.geoip import available
    from backend.app.models.security_event import SecurityEvent
    now = now or datetime.utcnow()
    since = now - timedelta(hours=24)
    recent = db.query(SecurityEvent).filter(SecurityEvent.ts >= since)

    def count(*events):
        return recent.filter(SecurityEvent.event.in_(events)).count()

    suspicious = (db.query(SecurityEvent.ip, func.count(SecurityEvent.id), func.max(SecurityEvent.ts),
                           func.max(SecurityEvent.country), func.count(func.distinct(SecurityEvent.email)))
                  .filter(SecurityEvent.ts >= since, SecurityEvent.event.in_(FAILURE_EVENTS),
                          SecurityEvent.ip.isnot(None))
                  .group_by(SecurityEvent.ip)
                  .having(func.count(SecurityEvent.id) >= SUSPICIOUS_FAILURES)
                  .order_by(func.count(SecurityEvent.id).desc()).limit(20).all())
    countries = (db.query(SecurityEvent.country, func.count(SecurityEvent.id))
                 .filter(SecurityEvent.ts >= since, SecurityEvent.event == 'login.success',
                         SecurityEvent.country.isnot(None))
                 .group_by(SecurityEvent.country).order_by(func.count(SecurityEvent.id).desc()).limit(8).all())
    return {
        'window_hours': 24,
        'sign_ins': count('login.success'),
        'failed_sign_ins': count(*FAILURE_EVENTS),
        'sign_ups': count('signup', 'hr.signup'),
        'unique_ips': recent.filter(SecurityEvent.ip.isnot(None)).with_entities(func.count(func.distinct(SecurityEvent.ip))).scalar() or 0,
        'admin_actions': recent.filter(SecurityEvent.event.like('admin.%'), SecurityEvent.event != 'admin.security_viewed').count(),
        'suspicious_ips': [{'ip': ip, 'failures': n, 'last_seen': last.isoformat() + 'Z', 'country': country, 'accounts': accounts}
                           for ip, n, last, country, accounts in suspicious],
        'top_countries': [{'country': c, 'sign_ins': n} for c, n in countries],
        'geolocation_enabled': available(),
        'retention_days': retention_days(),
        'event_types': EVENTS,
    }


def retention_days() -> int:
    import os
    try:
        return max(1, int(os.getenv('SECURITY_EVENT_RETENTION_DAYS', '90')))
    except ValueError:
        return 90
