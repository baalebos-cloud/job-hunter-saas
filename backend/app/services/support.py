"""Help & support: notification emails and serialisation.

Every request triggers two emails: a confirmation with the request number to
the person who wrote in, and an alert to the support inbox (SUPPORT_EMAIL)
whose Reply-To is the requester, so support can answer from the inbox too.
Answers written in the Owner console are emailed to the requester and shown
under "My requests". All user text is HTML-escaped before it goes into mail.
"""
from __future__ import annotations

import html
import logging

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

CATEGORY_LABELS = {
    'question': 'General question', 'bug': 'Something is not working', 'feedback': 'Feedback or idea',
    'billing': 'Plans and billing', 'account': 'Account and sign-in', 'resume': 'Resume tailoring',
    'jobs': 'Jobs and applications', 'other': 'Something else',
}
STATUS_LABELS = {'open': 'Waiting for support', 'answered': 'Answered', 'solved': 'Solved'}


def _iso(value):
    return value.isoformat() + 'Z' if value else None


def serialize(ticket, *, messages: bool = False, staff: bool = False) -> dict:
    out = {
        'id': ticket.id, 'number': ticket.number, 'category': ticket.category,
        'category_label': CATEGORY_LABELS.get(ticket.category, ticket.category),
        'subject': ticket.subject, 'status': ticket.status, 'status_label': STATUS_LABELS.get(ticket.status, ticket.status),
        'created_at': _iso(ticket.created_at), 'updated_at': _iso(ticket.updated_at),
        'last_reply_at': _iso(ticket.last_reply_at), 'has_attachment': bool(ticket.attachment),
        'message_count': len(ticket.messages), 'priority': bool(ticket.priority),
    }
    if staff:
        out.update({'email': ticket.email, 'name': ticket.name, 'user_id': ticket.user_id,
                    'page': ticket.page, 'user_agent': ticket.user_agent})
    if messages:
        out['messages'] = [{'id': m.id, 'author': m.author, 'body': m.body, 'created_at': _iso(m.created_at)}
                           for m in ticket.messages]
    elif ticket.messages:
        out['preview'] = ticket.messages[-1].body[:160]
    return out


def _layout(title: str, body_html: str) -> str:
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="font-family:Inter,Arial,sans-serif;background:#f8fafc;padding:32px 16px;margin:0;">
  <div style="max-width:600px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;padding:28px;">
    <div style="font-weight:800;color:#0f172a;font-size:18px;margin-bottom:18px;">baalebos<span style="color:#10b981;">.</span></div>
    <h1 style="font-size:18px;color:#0f172a;margin:0 0 14px;">{html.escape(title)}</h1>
    {body_html}
    <p style="color:#94a3b8;font-size:12px;margin-top:28px;border-top:1px solid #f1f5f9;padding-top:14px;">
      Baalebos Cloud support · <a href="mailto:{settings.SUPPORT_EMAIL}" style="color:#059669;">{settings.SUPPORT_EMAIL}</a>
    </p>
  </div>
</body></html>"""


def _quote(text: str) -> str:
    safe = html.escape(text).replace('\n', '<br>')
    return (f'<div style="background:#f8fafc;border-left:3px solid #10b981;border-radius:8px;padding:12px 14px;'
            f'color:#334155;font-size:14px;line-height:1.6;">{safe}</div>')


def _link(path: str = '/help') -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}{path}"


def _deliver(to: str, subject: str, body: str, reply_to: str | None = None) -> bool:
    from backend.app.utils import email
    try:
        return email.send_account_message(to, subject, body, **({'reply_to': reply_to} if reply_to else {}))
    except Exception as exc:     # never let mail failure break the request
        logger.warning('support_email_failed error_type=%s', type(exc).__name__)
        return False


def notify_created(ticket, message: str) -> None:
    """Confirmation to the requester and an alert to the support inbox."""
    greeting = html.escape(ticket.name.split()[0]) if ticket.name else 'there'
    _deliver(ticket.email, f'[{ticket.number}] We received your request: {ticket.subject}', _layout(
        'We have your request',
        f'<p style="color:#475569;font-size:14px;line-height:1.6;">Hi {greeting}, thanks for getting in touch. '
        f'Your request number is <strong>{ticket.number}</strong>. We usually reply within one business day, '
        f'by email and under <a href="{_link()}" style="color:#059669;">Help &amp; support → My requests</a>.</p>'
        f'<p style="color:#64748b;font-size:13px;margin:16px 0 6px;"><strong>{html.escape(ticket.subject)}</strong> · '
        f'{html.escape(CATEGORY_LABELS.get(ticket.category, ticket.category))}</p>{_quote(message)}'))
    details = ''.join(
        f'<tr><td style="color:#64748b;padding:3px 12px 3px 0;">{k}</td><td style="color:#0f172a;">{html.escape(str(v))}</td></tr>'
        for k, v in (('Subject', ticket.subject), ('From', f"{ticket.name or ''} <{ticket.email}>".strip()),
                     ('Account', f'user #{ticket.user_id}' if ticket.user_id else 'not signed in'),
                     ('Category', CATEGORY_LABELS.get(ticket.category, ticket.category)),
                     ('Page', ticket.page or '—'), ('Browser', ticket.user_agent or '—'),
                     ('Screenshot', 'attached in the console' if ticket.attachment else 'none')))
    tag = '[Priority] ' if ticket.priority else ''
    _deliver(settings.SUPPORT_EMAIL, f'{tag}[{ticket.number}] {ticket.subject}', _layout(
        f'New {"priority (Enterprise) " if ticket.priority else ""}support request {ticket.number}',
        f'<table style="font-size:13px;margin-bottom:14px;">{details}</table>{_quote(message)}'
        f'<p style="font-size:13px;color:#475569;margin-top:16px;">Reply in the '
        f'<a href="{_link("/admin?tab=support")}" style="color:#059669;">Owner console → Support</a> '
        f'so the answer is kept with the request, or reply to this email.</p>'), reply_to=ticket.email)


def notify_follow_up(ticket, message: str) -> None:
    """The requester added a message to an existing request."""
    _deliver(settings.SUPPORT_EMAIL, f'[{ticket.number}] New reply: {ticket.subject}', _layout(
        f'{ticket.number}: the requester replied', f'{_quote(message)}'
        f'<p style="font-size:13px;color:#475569;margin-top:16px;"><a href="{_link("/admin?tab=support")}" '
        f'style="color:#059669;">Open in the Owner console</a></p>'), reply_to=ticket.email)


def notify_answer(ticket, message: str) -> None:
    """An answer from support, emailed to the requester."""
    solved = ticket.status == 'solved'
    _deliver(ticket.email, f'[{ticket.number}] Re: {ticket.subject}', _layout(
        'Support replied to your request', f'{_quote(message)}'
        f'<p style="color:#475569;font-size:14px;line-height:1.6;margin-top:16px;">'
        + ('We have marked this request as solved. If you still need help, just reply under '
           if solved else 'You can reply under ')
        + f'<a href="{_link()}" style="color:#059669;">Help &amp; support → My requests</a> '
        f'or by answering this email.</p>'), reply_to=settings.SUPPORT_EMAIL)


# ── Dedicated Slack support (Enterprise) ──────────────────────────────────────

SLACK_PLAN_LABELS = {'paid': 'Paid Slack plan', 'free': 'Free Slack plan', 'none': 'No Slack yet'}
SLACK_STATUS_LABELS = {'requested': 'Requested', 'invited': 'Invitation sent', 'connected': 'Connected',
                       'closed': 'Closed'}


def serialize_slack(row, *, staff: bool = False) -> dict:
    out = {'id': row.id, 'company': row.company, 'slack_plan': row.slack_plan,
           'slack_plan_label': SLACK_PLAN_LABELS.get(row.slack_plan, row.slack_plan), 'emails': list(row.emails or []),
           'status': row.status, 'status_label': SLACK_STATUS_LABELS.get(row.status, row.status),
           'channel_name': row.channel_name, 'staff_note': row.staff_note,
           'created_at': _iso(row.created_at), 'updated_at': _iso(row.updated_at)}
    if staff:
        out.update(message=row.message, account_id=row.account_id)
    return out


def notify_slack_requested(row, requester_email: str) -> None:
    people = ', '.join(row.emails or [])
    _deliver(requester_email, 'We received your Slack support request', _layout(
        'Your Slack support request is in',
        f'<p style="color:#475569;font-size:14px;line-height:1.6;">Thanks. We will set up a shared Slack channel for '
        f'<strong>{html.escape(row.company)}</strong> and invite: {html.escape(people)}. You will get an email from us, and '
        f'an invitation from Slack, when it is ready. You can follow the status under '
        f'<a href="{_link()}" style="color:#059669;">Help &amp; support</a>.</p>'))
    details = ''.join(
        f'<tr><td style="color:#64748b;padding:3px 12px 3px 0;">{k}</td><td style="color:#0f172a;">{html.escape(str(v))}</td></tr>'
        for k, v in (('Company', row.company), ('Their Slack', SLACK_PLAN_LABELS.get(row.slack_plan, row.slack_plan)),
                     ('Invite', people), ('Requested by', requester_email), ('Account', f'user #{row.account_id}')))
    _deliver(settings.SUPPORT_EMAIL, f'[Priority] Slack channel request: {row.company}', _layout(
        'New Slack support request (Enterprise)',
        f'<table style="font-size:13px;margin-bottom:14px;">{details}</table>'
        + (_quote(row.message) if row.message else '')
        + f'<p style="font-size:13px;color:#475569;margin-top:16px;">Follow the setup checklist in the '
        f'<a href="{_link("/admin?tab=slack")}" style="color:#059669;">Owner console → Slack</a>, then mark the request '
        f'as invited there; the customer is emailed automatically.</p>'), reply_to=requester_email)


def notify_slack_invited(row, requester_email: str) -> None:
    channel = f'#{html.escape(row.channel_name)}' if row.channel_name else 'your support channel'
    note = _quote(row.staff_note) if row.staff_note else ''
    _deliver(requester_email, 'Your Baalebos Slack support channel is ready', _layout(
        'Your Slack channel is ready',
        f'<p style="color:#475569;font-size:14px;line-height:1.6;">We invited your team to {channel} with Slack Connect. '
        f'Look for an email from Slack (or a notice in your Slack workspace) and accept the invitation. '
        f'A Slack admin on your side may need to approve it.</p>{note}'
        f'<p style="color:#475569;font-size:14px;line-height:1.6;margin-top:16px;">Email and '
        f'<a href="{_link()}" style="color:#059669;">Help &amp; support</a> remain available too.</p>'),
        reply_to=settings.SUPPORT_EMAIL)
