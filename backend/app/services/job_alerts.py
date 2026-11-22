"""Job alert digests: scoring, the email itself, and one-click unsubscribe.

Match % is the same figure the job board shows: the share of a job's listed
skills found in the candidate's own resume or profile. A posting that lists
fewer than three skills gets no percentage ("Match not available") rather
than a guess. All job and user text is HTML-escaped.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import html
from urllib.parse import quote

from backend.app.core.config import settings

MAX_JOBS = 10
FREQUENCIES = ("daily", "weekly")
MIN_MATCHES = (0, 50, 70)


# ── One-click unsubscribe ────────────────────────────────────────────────────

def _signature(user_id: int, email: str) -> str:
    message = f"job-alerts-unsubscribe:{user_id}:{(email or '').lower()}".encode()
    digest = hmac.new((settings.SECRET_KEY or '').encode(), message, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest[:18]).decode().rstrip('=')


def unsubscribe_token(user) -> str:
    """Opaque, per-user token. Changing the account email invalidates it."""
    return f"{user.id}.{_signature(user.id, user.email)}"


def user_from_token(db, token: str):
    from backend.app.models.user import User
    try:
        raw_id, signature = (token or '').split('.', 1)
        user = db.get(User, int(raw_id))
    except (ValueError, TypeError):
        return None
    if user is None or not hmac.compare_digest(signature, _signature(user.id, user.email)):
        return None
    return user


def unsubscribe_links(user) -> dict:
    token = quote(unsubscribe_token(user))
    page = f"{settings.FRONTEND_URL.rstrip('/')}/unsubscribe?t={token}"
    links = {'page': page, 'headers': {'List-Unsubscribe': f'<{page}>'}}
    api = (settings.API_PUBLIC_URL or '').rstrip('/')
    if api.startswith('https://'):
        # RFC 8058: mail apps POST here when the reader clicks their own "Unsubscribe" button.
        one_click = f"{api}/api/v1/alerts/unsubscribe?t={token}"
        links['headers'] = {'List-Unsubscribe': f'<{one_click}>, <{page}>',
                            'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click'}
    return links


# ── Scoring ──────────────────────────────────────────────────────────────────

def score(job, mine: set[str]) -> dict:
    """{'score': int|None, 'matched': [...], 'missing': [...], 'total': n}"""
    from backend.app.routes.job_board import job_skills, match
    skills = job_skills(job)
    result = match(skills, mine)
    if result is None:
        return {'score': None, 'matched': [], 'missing': [], 'total': len(skills)}
    return {**result, 'total': len(skills)}


def rank(scored: list[tuple]) -> list[tuple]:
    """Best match first; unscored postings after scored ones; newest first within a tie."""
    return sorted(scored, key=lambda item: (item[1]['score'] is not None, item[1]['score'] or 0,
                                            item[0].first_seen_at or item[0].scraped_at), reverse=True)


# ── Email ────────────────────────────────────────────────────────────────────

def _job_url(job) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/jobs?job={job.id}"


def _where(job) -> str:
    parts = [job.company or 'Company not provided', job.location or 'Location not specified']
    if job.salary_range:
        parts.append(job.salary_range)
    return ' · '.join(parts)


def subject_line(ranked: list[tuple]) -> str:
    count = len(ranked)
    best = max((s['score'] for _, s in ranked if s['score'] is not None), default=None)
    noun = 'job matches' if count == 1 else 'jobs match'
    return f"{count} new {noun} your profile" + (f" (best {best}%)" if best is not None else '')


def build_digest(user, ranked: list[tuple], frequency: str) -> dict:
    """Returns {'subject', 'text', 'html'} for up to MAX_JOBS ranked (job, score) pairs."""
    e = html.escape
    links = unsubscribe_links(user)
    first = (user.full_name or '').split()[0] if user.full_name else 'there'
    work = {'remote': 'Remote', 'hybrid': 'Hybrid', 'onsite': 'On-site'}.get(user.job_alert_work_type)
    criteria = ' · '.join(p for p in (user.career_track, work, f"open to {user.country}" if user.country else None) if p)

    text = [f"{len(ranked)} new jobs match your role and location preferences.", ""]
    cards = []
    for job, s in ranked[:MAX_JOBS]:
        kind = "Apply on Baalebos" if job.posted_by_hr and not job.url else "Complete the employer's application form"
        pct = f"{s['score']}% match" if s['score'] is not None else "Match not available"
        text.append(f"{pct}: {job.title} at {job.company} — {job.location or 'Location not specified'}\n{kind}. Job ID: {job.id}\n")
        if s['score'] is not None:
            have = (f"You have {len(s['matched'])} of its {s['total']} listed skills: "
                    + e(', '.join(s['matched'][:6])) if s['matched'] else f"None of its {s['total']} listed skills are in your resume or profile yet.")
            missing = f"<br><span style=\"color:#92400e\">Missing: {e(', '.join(s['missing'][:3]))}</span>" if s['missing'] else ''
            chip_bg, chip_fg = ('#ecfdf5', '#047857') if s['score'] >= 50 else ('#fffbeb', '#92400e')
            detail = f'<div style="font-size:13px;color:#065f46;background:#ecfdf5;border-radius:8px;padding:8px 10px;margin-top:8px">{have}{missing}</div>'
        else:
            chip_bg, chip_fg = '#f1f5f9', '#334155'
            detail = ('<div style="font-size:13px;color:#475569;background:#f8fafc;border-radius:8px;padding:8px 10px;margin-top:8px">'
                      'This posting lists too few skills to score fairly. It matches your role and location.</div>')
        employer = ('<span style="font-size:11px;font-weight:700;color:#047857;background:#ecfdf5;border-radius:999px;'
                    'padding:2px 8px;margin-left:6px">Hiring on Baalebos</span>') if job.posted_by_hr else ''
        cards.append(f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e2e8f0;border-radius:12px;margin:12px 0">
<tr><td style="padding:14px 16px;font-family:Arial,sans-serif">
<div><span style="font-size:12px;font-weight:700;color:{chip_fg};background:{chip_bg};border-radius:999px;padding:3px 9px;margin-right:6px">{e(pct)}</span>
<strong style="font-size:15px;color:#0f172a">{e(job.title or '')}</strong>{employer}</div>
<div style="font-size:14px;color:#475569;margin-top:4px">{e(_where(job))}</div>
{detail}
<a href="{e(_job_url(job))}" style="display:inline-block;margin-top:10px;background:#0f172a;color:#ffffff;text-decoration:none;font-weight:700;font-size:13px;padding:8px 14px;border-radius:10px">View job</a>
</td></tr></table>""")

    text += [f"See the job feed: {settings.FRONTEND_URL.rstrip('/')}/jobs",
             "Match % = share of the job's listed skills found in your resume or profile. "
             "Review the full requirements and location restrictions before applying. A match is not a hiring or eligibility assessment.",
             f"Turn off job alerts in one click: {links['page']}"]

    body = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="margin:0;background:#f1f5f9;padding:24px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border:1px solid #e2e8f0;border-radius:16px">
<tr><td style="padding:22px 24px 4px;font-family:Arial,sans-serif;font-size:18px;font-weight:800;color:#0f172a">baalebos<span style="color:#10b981">.</span></td></tr>
<tr><td style="padding:4px 24px 20px;font-family:Arial,sans-serif">
<p style="margin:8px 0 4px;font-size:15px;color:#0f172a">Hi {e(first)},</p>
<p style="margin:0;font-size:14px;color:#475569">{len(ranked)} new {'job' if len(ranked) == 1 else 'jobs'} since your last {'weekly' if frequency == 'weekly' else 'daily'} alert match <strong>{e(criteria)}</strong>, best match first.</p>
{''.join(cards)}
<p style="font-size:12px;color:#64748b;margin:14px 0 0">Match % = share of the job's listed skills found in your resume or profile. It is a guide, not a hiring decision. Check each posting's requirements and location rules before applying.</p>
</td></tr>
<tr><td style="border-top:1px solid #f1f5f9;padding:14px 24px 20px;font-family:Arial,sans-serif;font-size:12px;color:#64748b">
You get this because you turned on job alerts ({e(frequency)}{', ' + str(user.job_alert_min_match) + '%+ matches' if user.job_alert_min_match else ', any match'}).
<a href="{e(settings.FRONTEND_URL.rstrip('/'))}/profile" style="color:#059669">Change preferences</a> ·
<a href="{e(links['page'])}" style="color:#059669">Unsubscribe in one click</a><br>Baalebos · {e(settings.SUPPORT_EMAIL)}
</td></tr></table></td></tr></table></body></html>"""
    return {'subject': subject_line(ranked), 'text': '\n'.join(text), 'html': body, 'headers': links['headers']}
