"""Email sent the moment an admin assigns, changes or removes someone's staff
role in Owner console -> Access control: what the role is for, what it can open,
and exactly what to do next."""
from __future__ import annotations

import html

from backend.app.core.config import settings
from backend.app.services.support import _deliver, _layout, _link

# Plain-language guide per role. ``where`` is the page the role works in.
ROLE_GUIDE = {
    'super_admin': {
        'label': 'Super admin', 'where': '/admin', 'place': 'Owner console',
        'summary': 'Full administration of Baalebos: users and staff roles, employers, jobs, security, support, '
                   'operations and audit.',
        'can': ['Everything in the Owner console', 'Assign and remove staff roles in Access control',
                'Security controls, audit log and operations'],
    },
    'product_manager': {
        'label': 'Product manager', 'where': '/admin', 'place': 'Team console',
        'summary': 'You own the product, go-to-market and customer support.',
        'can': ['Overview: product numbers and trends', 'Growth: funnel, plans, estimated revenue, referrals, '
                'job alert emails and campaign results', 'Content: job insights and ready-to-copy social posts',
                'Support and Slack: read and answer customer requests (these contain customer contact details)'],
    },
    'social_media_manager': {
        'label': 'Social media manager', 'where': '/admin', 'place': 'Team console',
        'summary': 'You run Baalebos on social media: content from live jobs and the results of each campaign. '
                   'No customer personal data is shown in your role.',
        'can': ['Overview: product totals and trends', 'Campaigns: sign-ups by tagged link and partner card clicks',
                'Content: job insights and ready-to-copy posts with tracked links'],
    },
    'legal_counsel': {
        'label': 'Legal counsel', 'where': '/admin', 'place': 'Team console',
        'summary': 'You look after Baalebos legal documents and data-protection requests.',
        'can': ['Legal: edit and publish the Terms, Privacy, Cookie, Refund and Acceptable Use policies',
                'Data-protection requests: export or erase a person\'s data', 'Read the audit trail',
                'Look up user accounts (read only)'],
    },
    'security_auditor': {
        'label': 'Security auditor', 'where': '/governance', 'place': 'Security & governance',
        'summary': 'Read-only review of security and the audit trail.',
        'can': ['Audit trail and exports', 'Service metrics and reports', 'View user accounts and roles'],
    },
    'engineering_lead': {
        'label': 'Engineering lead', 'where': '/governance', 'place': 'Security & governance',
        'summary': 'Operational health and diagnostics of the platform.',
        'can': ['Service metrics and reports', 'Provider and infrastructure diagnostics', 'Job listing moderation'],
    },
    'compliance_officer': {
        'label': 'Compliance officer', 'where': '/governance', 'place': 'Security & governance',
        'summary': 'GDPR and SOC 2 evidence, and data-subject requests.',
        'can': ['Audit trail and exports', 'Reports', 'Data export and erasure requests', 'View user accounts and roles'],
    },
    'viewer': {
        'label': 'Viewer', 'where': '/governance', 'place': 'Security & governance',
        'summary': 'Read-only dashboards.',
        'can': ['Service metrics', 'Reports'],
    },
}


def role_label(role: str | None) -> str:
    return ROLE_GUIDE.get(role or '', {}).get('label') or (role or 'no staff role')


def _steps(guide: dict, two_step_on: bool) -> list[str]:
    steps = ['Sign in again at ' + _link('/login') + '. For your security, you were signed out on all devices '
             'when your access changed.']
    if not two_step_on:
        steps.append('Turn on two-step verification when asked. Staff pages open only after it is on; keep an '
                     'authenticator app (for example Google Authenticator or 1Password) ready.')
    steps.append(f"Open {guide['place']}: {_link(guide['where'])}. You will see only the sections your role allows.")
    steps.append(f'Questions about your access? Reply to this email or write to {settings.SUPPORT_EMAIL}.')
    return steps


def role_assigned_message(user, role: str, assigned_by: str | None) -> tuple[str, str]:
    guide = ROLE_GUIDE.get(role) or {'label': role, 'where': '/admin', 'place': 'the console',
                                     'summary': 'A staff role on Baalebos.', 'can': []}
    first = html.escape((user.full_name or '').split()[0]) if user.full_name else 'there'
    by = f' by {html.escape(assigned_by)}' if assigned_by else ''
    can = ''.join(f'<li style="margin:4px 0;">{html.escape(item)}</li>' for item in guide['can'])
    steps = ''.join(f'<li style="margin:6px 0;">{html.escape(step)}</li>'
                    for step in _steps(guide, bool(getattr(user, 'totp_enabled_at', None))))
    body = (
        f'<p style="color:#475569;font-size:14px;line-height:1.6;">Hi {first}, you have been given the '
        f'<strong>{html.escape(guide["label"])}</strong> role on Baalebos{by}.</p>'
        f'<p style="color:#475569;font-size:14px;line-height:1.6;">{html.escape(guide["summary"])}</p>'
        + (f'<p style="color:#0f172a;font-size:14px;font-weight:600;margin:16px 0 4px;">What you can open</p>'
           f'<ul style="color:#475569;font-size:14px;line-height:1.5;padding-left:20px;margin:0;">{can}</ul>' if can else '')
        + f'<p style="color:#0f172a;font-size:14px;font-weight:600;margin:16px 0 4px;">What to do next</p>'
          f'<ol style="color:#475569;font-size:14px;line-height:1.5;padding-left:20px;margin:0;">{steps}</ol>'
          f'<p style="margin:20px 0 0;"><a href="{_link(guide["where"])}" style="background:#059669;color:#fff;'
          f'text-decoration:none;font-weight:600;padding:11px 18px;border-radius:10px;display:inline-block;">'
          f'Open {html.escape(guide["place"])}</a></p>'
          f'<p style="color:#94a3b8;font-size:12px;margin-top:18px;">If you did not expect this, tell us at '
          f'{html.escape(settings.SUPPORT_EMAIL)} so we can check the change.</p>')
    return f'You are now a {guide["label"]} on Baalebos', _layout(f'Your new role: {guide["label"]}', body)


def role_removed_message(user, previous: str | None) -> tuple[str, str]:
    first = html.escape((user.full_name or '').split()[0]) if user.full_name else 'there'
    body = (f'<p style="color:#475569;font-size:14px;line-height:1.6;">Hi {first}, your '
            f'<strong>{html.escape(role_label(previous))}</strong> role on Baalebos has been removed, so the staff '
            f'pages are no longer available to you. Your own Baalebos account, resumes and applications are '
            f'unchanged; sign in again to keep using them.</p>'
            f'<p style="color:#94a3b8;font-size:12px;margin-top:18px;">If you think this is a mistake, write to '
            f'{html.escape(settings.SUPPORT_EMAIL)}.</p>')
    return 'Your Baalebos staff role was removed', _layout('Your staff role was removed', body)


def send_role_change(user, previous: str | None, role: str | None, assigned_by: str | None = None) -> bool:
    """Email the person whose role changed. Never raises (mail must not break the change)."""
    if role:
        subject, body = role_assigned_message(user, role, assigned_by)
    elif previous:
        subject, body = role_removed_message(user, previous)
    else:
        return False
    return _deliver(user.email, subject, body, reply_to=settings.SUPPORT_EMAIL)
