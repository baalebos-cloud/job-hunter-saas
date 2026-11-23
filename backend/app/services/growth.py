"""Team console figures: product analytics, go-to-market (growth), campaign
results and content insights. Every figure is computed from the platform's own
records; nothing is estimated except monthly revenue, which is labelled as an
estimate at list price. No personal data leaves these functions."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.application import Application
from backend.app.models.automation import AutomationEvent
from backend.app.models.growth import PARTNERS, GrowthCounter
from backend.app.models.job import Job
from backend.app.models.referral import Referral
from backend.app.models.resume import Resume
from backend.app.models.subscription import PLANS, Subscription
from backend.app.models.user import User

PAID = ('pro', 'enterprise')


def _pct(part, whole):
    return round(100 * part / whole, 1) if whole else None


def _tailored(db):
    return db.query(Resume).filter(Resume.status == 'completed', Resume.filename.like('optimized_%'))


def _candidates(db):
    """Job seekers: not employer accounts and not platform staff."""
    return db.query(User).filter(User.is_hr.isnot(True), User.role.is_(None))


def _daily(rows, days, today):
    counts = Counter(r for r in rows if r)
    return [{'date': (today - timedelta(days=i)).isoformat(), 'count': counts.get(today - timedelta(days=i), 0)}
            for i in range(days - 1, -1, -1)]


def _dates(query, column, since):
    return [d.date() if isinstance(d, datetime) else d for (d,) in query.with_entities(column).filter(column >= since)]


# ── Product analytics (analytics:read) ───────────────────────────────────────

def analytics(db: Session, days: int = 30) -> dict:
    now = datetime.utcnow()
    today, week = now.date(), now - timedelta(days=7)
    since = datetime.combine(today - timedelta(days=days - 1), datetime.min.time())
    users = _candidates(db)
    return {
        'kpis': {
            'users': users.count(), 'users_this_week': users.filter(User.created_at >= week).count(),
            'verified_users': users.filter(User.is_verified.is_(True)).count(),
            'resumes_tailored': _tailored(db).count(),
            'resumes_this_week': _tailored(db).filter(Resume.created_at >= week).count(),
            'applications': db.query(Application).count(),
            'applications_this_week': db.query(Application).filter(Application.created_at >= week).count(),
            'live_jobs': db.query(Job).filter(Job.is_active.is_(True)).count(),
            'new_jobs_this_week': db.query(Job).filter(Job.first_seen_at >= week).count(),
            'employer_jobs': db.query(Job).filter(Job.posted_by_hr.is_(True), Job.is_active.is_(True)).count(),
            'alert_subscribers': users.filter(User.job_alerts_enabled.is_(True)).count(),
        },
        'daily': {
            'signups': _daily(_dates(users, User.created_at, since), days, today),
            'resumes': _daily(_dates(_tailored(db), Resume.created_at, since), days, today),
            'applications': _daily(_dates(db.query(Application), Application.created_at, since), days, today),
        },
        'days': days,
    }


# ── Go-to-market (growth:read) ───────────────────────────────────────────────

def _counter_total(db, kind, since):
    return int(db.query(func.coalesce(func.sum(GrowthCounter.count), 0))
               .filter(GrowthCounter.kind == kind, GrowthCounter.day >= since).scalar() or 0)


def _tracked_since(db, prefix):
    first = db.query(func.min(GrowthCounter.day)).filter(GrowthCounter.kind.like(f'{prefix}%')).scalar()
    return first.isoformat() if first else None


def growth(db: Session, days: int = 30) -> dict:
    now = datetime.utcnow()
    since = now - timedelta(days=days)
    cohort = _candidates(db).filter(User.created_at >= since)
    ids = [uid for (uid,) in cohort.with_entities(User.id)]
    signed_up = len(ids)

    def among(query, column):
        return query.filter(column.in_(ids)).with_entities(column).distinct().count() if ids else 0
    verified = cohort.filter(User.is_verified.is_(True)).count()
    tailored = among(_tailored(db), Resume.owner_id)
    applied = among(db.query(Application), Application.user_id)
    paid = (db.query(Subscription).filter(Subscription.user_id.in_(ids), Subscription.plan.in_(PAID),
                                          Subscription.status == 'active').count() if ids else 0)
    steps = [('Signed up', signed_up), ('Verified email', verified), ('Tailored a resume', tailored),
             ('Applied to a job', applied), ('On a paid plan', paid)]

    weeks = []
    for i in range(11, -1, -1):
        start = (now - timedelta(days=now.weekday(), weeks=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)
        weeks.append({'week': start.date().isoformat(),
                      'signups': _candidates(db).filter(User.created_at >= start, User.created_at < end).count(),
                      'resumes': _tailored(db).filter(Resume.created_at >= start, Resume.created_at < end).count()})

    active_paid = dict(db.query(Subscription.plan, func.count(Subscription.id))
                       .filter(Subscription.plan.in_(PAID), Subscription.status == 'active')
                       .group_by(Subscription.plan).all())
    est_mrr = sum(active_paid.get(p, 0) * PLANS[p]['price'] for p in PAID)
    day0 = since.date()
    referral_window = db.query(Referral).filter(Referral.created_at >= since)
    return {
        'days': days,
        'funnel': [{'step': name, 'count': count, 'pct': _pct(count, signed_up)} for name, count in steps],
        'weekly': weeks,
        'plans': {
            'pro': active_paid.get('pro', 0), 'enterprise': active_paid.get('enterprise', 0),
            'free': max(_candidates(db).count() - sum(active_paid.values()), 0),
            'estimated_mrr': est_mrr, 'currency': 'USD',
            'mrr_note': 'Estimate: active paid plans x list price ($19 Pro, $49 Enterprise). Stripe is the source of truth.',
            'upgrades': _counter_total(db, 'plan:upgraded', day0),
            'cancellations': _counter_total(db, 'plan:cancelled', day0),
            'payment_failures': _counter_total(db, 'plan:payment_failed', day0),
            'changes_tracked_since': _tracked_since(db, 'plan:'),
        },
        'referrals': {
            'invites': referral_window.count(),
            'signed_up': referral_window.filter(Referral.referred_user_id.isnot(None)).count(),
            'converted': db.query(Referral).filter(Referral.converted_at >= since).count(),
        },
        'alerts': {
            'subscribers': _candidates(db).filter(User.job_alerts_enabled.is_(True)).count(),
            'sent_7d': db.query(AutomationEvent).filter(AutomationEvent.event_type == 'jobs.matched',
                                                        AutomationEvent.status == 'sent',
                                                        AutomationEvent.sent_at >= now - timedelta(days=7)).count(),
            'sent_30d': db.query(AutomationEvent).filter(AutomationEvent.event_type == 'jobs.matched',
                                                         AutomationEvent.status == 'sent',
                                                         AutomationEvent.sent_at >= now - timedelta(days=30)).count(),
            'unsubscribed': _counter_total(db, 'alerts:unsubscribed', day0),
            'unsubscribes_tracked_since': _tracked_since(db, 'alerts:'),
        },
    }


def growth_csv_rows(data: dict) -> list[list]:
    rows = [['section', 'metric', 'value']]
    rows += [['funnel', f['step'], f['count']] for f in data['funnel']]
    rows += [['plans', k, v] for k, v in data['plans'].items() if k != 'mrr_note']
    rows += [['referrals', k, v] for k, v in data['referrals'].items()]
    rows += [['job_alerts', k, v] for k, v in data['alerts'].items()]
    rows += [['weekly', w['week'], f"signups={w['signups']}; resumes={w['resumes']}"] for w in data['weekly']]
    return rows


# ── Campaign results (campaigns:read) ────────────────────────────────────────

def campaigns(db: Session, days: int = 90) -> dict:
    now = datetime.utcnow()
    since = now - timedelta(days=days)
    rows = (_candidates(db).filter(User.created_at >= since)
            .with_entities(User.id, User.is_verified, User.signup_utm_source, User.signup_utm_medium,
                           User.signup_utm_campaign, User.signup_referrer).all())
    paid_ids = {uid for (uid,) in db.query(Subscription.user_id).filter(
        Subscription.plan.in_(PAID), Subscription.status == 'active')}
    groups = defaultdict(lambda: {'signups': 0, 'verified': 0, 'paid': 0})
    referrers = defaultdict(lambda: {'signups': 0, 'verified': 0, 'paid': 0})
    for row in rows:
        key = (row.signup_utm_source or '(direct or untagged)', row.signup_utm_medium or '', row.signup_utm_campaign or '')
        for bucket in [groups[key]] + ([referrers[row.signup_referrer]] if row.signup_referrer else []):
            bucket['signups'] += 1
            bucket['verified'] += 1 if row.is_verified else 0
            bucket['paid'] += 1 if row.id in paid_ids else 0
    sources = sorted(({'source': s, 'medium': m, 'campaign': c, **v} for (s, m, c), v in groups.items()),
                     key=lambda r: (-r['signups'], r['source']))
    today = now.date()
    clicks = defaultdict(lambda: defaultdict(int))
    for kind, day, count in db.query(GrowthCounter.kind, GrowthCounter.day, GrowthCounter.count).filter(
            GrowthCounter.kind.like('partner_click:%'), GrowthCounter.day >= today - timedelta(days=29)):
        clicks[kind.split(':', 1)[1]][day] += count
    partners = [{'partner': p, 'clicks_7d': sum(c for d, c in clicks[p].items() if d >= today - timedelta(days=6)),
                 'clicks_30d': sum(clicks[p].values()),
                 'daily': [{'date': (today - timedelta(days=i)).isoformat(), 'count': clicks[p].get(today - timedelta(days=i), 0)}
                           for i in range(29, -1, -1)]} for p in PARTNERS]
    return {'days': days, 'total_signups': len(rows), 'sources': sources,
            'referrers': sorted(({'referrer': r, **v} for r, v in referrers.items()), key=lambda r: -r['signups'])[:10],
            'partners': partners, 'clicks_tracked_since': _tracked_since(db, 'partner_click:'),
            'how_to_tag': f"{settings.FRONTEND_URL.rstrip('/')}/?utm_source=linkedin&utm_medium=social&utm_campaign=launch"}


# ── Content insights (content:read) ──────────────────────────────────────────

_MONEY = re.compile(r'[$£€]\s?(\d[\d,]*(?:\.\d+)?)\s*([kK])?')


def salary_top(text) -> float | None:
    """Highest annual amount in a salary text ("$120K – $160K" -> 160000). Hourly or
    monthly figures are skipped so they are never ranked against yearly pay."""
    text = str(text or '')
    if not text or re.search(r'(/\s*(hr|hour|h|mo|month|day)\b)|\b(hourly|per hour|monthly|per month|daily)\b', text, re.I):
        return None
    values = []
    for number, k in _MONEY.findall(text):
        value = float(number.replace(',', '')) * (1000 if k else 1)
        if value >= 10000:
            values.append(value)
    return max(values) if values else None


def _job_link(job_id, campaign):
    return (f"{settings.FRONTEND_URL.rstrip('/')}/jobs?job={job_id}"
            f"&utm_source=social&utm_medium=post&utm_campaign={campaign}")


def content(db: Session) -> dict:
    from backend.app.routes.job_board import _one_per_role
    now = datetime.utcnow()
    week = now - timedelta(days=7)
    rows = (db.query(Job).filter(Job.is_active.is_(True))
            .order_by(Job.posted_by_hr.desc(), func.coalesce(Job.published_at, Job.first_seen_at, Job.scraped_at).desc())
            .all())
    jobs = _one_per_role(rows)
    new = [j for j in jobs if (j.first_seen_at or j.scraped_at or datetime.min) >= week]
    remote_new = [j for j in new if j.work_type == 'remote']
    companies = Counter(j.company for j in jobs if j.company)

    def card(job, campaign):
        return {'id': job.id, 'title': job.title, 'company': job.company, 'location': job.location,
                'work_type': job.work_type, 'salary': job.salary_range, 'link': _job_link(job.id, campaign)}
    newest_remote = [card(j, 'remote_roles') for j in [j for j in jobs if j.work_type == 'remote'][:8]]
    paid = sorted(((salary_top(j.salary_range), j) for j in jobs), key=lambda p: -(p[0] or 0))
    top_paid = [{**card(j, 'top_paid'), 'salary_top': amount} for amount, j in paid if amount][:8]
    top_companies = [{'company': c, 'open_roles': n} for c, n in companies.most_common(10)]

    site = f"{settings.FRONTEND_URL.rstrip('/')}/jobs?utm_source=social&utm_medium=post&utm_campaign="
    posts = []
    if new:
        lines = '\n'.join(f'• {j.title} at {j.company}' for j in new[:5] if j.company)
        posts.append({'id': 'weekly_roundup', 'title': 'Weekly new jobs', 'text': (
            f"🚀 {len(new)} new tech jobs on Baalebos this week"
            + (f", {len(remote_new)} of them remote" if remote_new else '') + ".\n\nHiring now:\n" + lines
            + f"\n\nTailor your resume to any of them in minutes: {site}weekly_roundup\n\n#TechJobs #Hiring #RemoteJobs")})
    if newest_remote:
        j = newest_remote[0]
        where = f" ({j['location']})" if j['location'] else ''
        pay = f"\nPay: {j['salary']}" if j['salary'] else ''
        posts.append({'id': 'remote_spotlight', 'title': 'Remote role spotlight', 'text': (
            f"🌍 Remote role spotlight: {j['title']} at {j['company']}{where}.{pay}\n\n"
            f"See the role and tailor your resume to it: {_job_link(j['id'], 'remote_spotlight')}\n\n#RemoteJobs #TechJobs")})
    if top_companies:
        listing = ', '.join(f"{c['company']} ({c['open_roles']} role{'s' if c['open_roles'] > 1 else ''})"
                            for c in top_companies[:5])
        posts.append({'id': 'who_is_hiring', 'title': "Who's hiring", 'text': (
            f"👀 Who's hiring on Baalebos right now: {listing}.\n\n"
            f"Browse {len(jobs)} live roles: {site}who_is_hiring\n\n#Hiring #TechJobs #Careers")})
    return {'live_jobs': len(jobs), 'new_this_week': len(new), 'remote_new_this_week': len(remote_new),
            'top_companies': top_companies, 'newest_remote': newest_remote, 'top_paid': top_paid, 'posts': posts,
            'note': 'Built only from live jobs on the board. Links carry campaign tags, so sign-ups from each post '
                    'show under Campaigns.'}
