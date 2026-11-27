"""Application forms for jobs posted on Baalebos.

Each employer decides, per job, which standard details to ask for (off,
optional or required) and adds their own questions. Candidates answer them when
they apply; the answers are stored with labels as a snapshot, so later edits to
the form never change an application that was already sent.

Nothing here rejects a candidate automatically: answers are shown to the
employer, and every decision stays with a person.
"""
from __future__ import annotations

import html
import re
import secrets
from datetime import date

from backend.app.utils.sanitize import sanitize_untrusted_text

FORM_VERSION = 1
MAX_QUESTIONS = 20
MAX_OPTIONS = 20
LEVELS = ('off', 'optional', 'required')
QUESTION_TYPES = {
    'short_text': 'Short answer', 'long_text': 'Paragraph', 'yes_no': 'Yes / No', 'single_choice': 'One choice',
    'multi_choice': 'Several choices', 'number': 'Number', 'date': 'Date', 'url': 'Link',
}
CHOICE_TYPES = ('single_choice', 'multi_choice')
TEXT_LIMITS = {'short_text': 300, 'long_text': 5000, 'url': 500}

# Standard details an employer can switch on. "{country}" is filled from the form.
STANDARD = {
    'cover_letter':       ('Cover letter', 'long_text'),
    'linkedin':           ('LinkedIn profile', 'url'),
    'portfolio':          ('Portfolio or GitHub link', 'url'),
    'city':               ('City you live in', 'short_text'),
    'experience_years':   ('Years of relevant experience', 'number'),
    'work_authorization': ('Are you authorised to work in {country}?', 'yes_no'),
    'sponsorship':        ('Will you need visa sponsorship?', 'yes_no'),
    'notice_period':      ('Notice period or earliest start date', 'short_text'),
    'expected_salary':    ('Expected salary (amount and currency)', 'short_text'),
    'relocate':           ('Are you willing to relocate?', 'yes_no'),
}
DEFAULT_STANDARD = {'cover_letter': 'optional', 'linkedin': 'optional'}
NUMBER_RANGES = {'std_experience_years': (0, 60)}
_ID = re.compile(r'^q_[a-z0-9]{6,16}$')
_DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_PHONE = re.compile(r'^\+?[0-9 ()\-.]{6,30}$')


class FormError(ValueError):
    """Answers that do not satisfy the form: a message per field id."""

    def __init__(self, fields: dict[str, str], message: str = 'Some answers need attention.'):
        super().__init__(message)
        self.fields = fields
        self.message = message


def _clean(value, limit: int) -> str:
    return sanitize_untrusted_text(value)[:limit].strip() if value is not None else ''


def default_form() -> dict:
    return {'version': FORM_VERSION, 'standard': dict(DEFAULT_STANDARD), 'authorization_country': '', 'questions': []}


def normalize_form(raw: dict | None) -> dict:
    """Check and tidy an employer's form. Raises ValueError with a readable message."""
    if raw is None:
        return default_form()
    if not isinstance(raw, dict):
        raise ValueError('The application form is not valid.')
    standard = {}
    for key, level in (raw.get('standard') or {}).items():
        if key not in STANDARD:
            raise ValueError(f'Unknown standard field "{key}".')
        if level not in LEVELS:
            raise ValueError(f'"{STANDARD[key][0]}" must be off, optional or required.')
        if level != 'off':
            standard[key] = level
    country = _clean(raw.get('authorization_country'), 60)
    if 'work_authorization' in standard and not country:
        raise ValueError('Say which country the work authorisation question is about.')
    questions_in = raw.get('questions') or []
    if not isinstance(questions_in, list):
        raise ValueError('Questions must be a list.')
    if len(questions_in) > MAX_QUESTIONS:
        raise ValueError(f'Add up to {MAX_QUESTIONS} questions per job.')
    questions, seen_ids, seen_labels = [], set(), set()
    for n, q in enumerate(questions_in, 1):
        if not isinstance(q, dict):
            raise ValueError(f'Question {n} is not valid.')
        label = _clean(q.get('label'), 300)
        if len(label) < 3:
            raise ValueError(f'Question {n} needs some text (at least 3 characters).')
        if label.casefold() in seen_labels:
            raise ValueError(f'Question {n} repeats an earlier question.')
        kind = q.get('type')
        if kind not in QUESTION_TYPES:
            raise ValueError(f'Question {n} has an unknown answer type.')
        options = []
        if kind in CHOICE_TYPES:
            for option in q.get('options') or []:
                text = _clean(option, 100)
                if text and text.casefold() not in {o.casefold() for o in options}:
                    options.append(text)
            if len(options) < 2:
                raise ValueError(f'Question {n} needs at least two choices.')
            if len(options) > MAX_OPTIONS:
                raise ValueError(f'Question {n} can have up to {MAX_OPTIONS} choices.')
        qid = q.get('id') if isinstance(q.get('id'), str) and _ID.match(q['id']) else ''
        while not qid or qid in seen_ids:
            qid = 'q_' + secrets.token_hex(4)
        seen_ids.add(qid)
        seen_labels.add(label.casefold())
        questions.append({'id': qid, 'label': label, 'type': kind, 'required': bool(q.get('required')),
                          'options': options, 'help': _clean(q.get('help'), 300)})
    return {'version': FORM_VERSION, 'standard': standard, 'authorization_country': country, 'questions': questions}


def form_of(job) -> dict:
    """The job's form; jobs posted before forms existed get the default one."""
    stored = getattr(job, 'application_form', None)
    if not stored:
        return default_form()
    try:
        return normalize_form(stored)
    except ValueError:
        return default_form()


def fields_for(form: dict) -> list[dict]:
    """Everything the candidate answers, in display order: standard details, then the employer's questions."""
    fields = []
    for key, (label, kind) in STANDARD.items():
        level = form['standard'].get(key)
        if level:
            fields.append({'id': f'std_{key}', 'label': label.format(country=form.get('authorization_country') or 'this country'),
                           'type': kind, 'required': level == 'required', 'options': [], 'help': '', 'standard': True})
    fields += [{**q, 'standard': False} for q in form['questions']]
    return fields


def _answer(field: dict, value):
    """Return the cleaned value (None when empty) or raise ValueError with the reason."""
    kind = field['type']
    if value is None or value == '' or value == []:
        return None
    if kind in ('short_text', 'long_text'):
        text = _clean(value if isinstance(value, str) else str(value), TEXT_LIMITS[kind] + 1)
        if len(text) > TEXT_LIMITS[kind]:
            raise ValueError(f'Keep this under {TEXT_LIMITS[kind]:,} characters.')
        return text or None
    if kind == 'url':
        text = _clean(str(value), 501)
        if len(text) > 500 or not re.match(r'^https://[^\s/$.?#][^\s]*$', text):
            raise ValueError('Enter a full link starting with https://')
        return text
    if kind == 'yes_no':
        if value not in ('yes', 'no'):
            raise ValueError('Choose yes or no.')
        return value
    if kind == 'single_choice':
        if value not in field['options']:
            raise ValueError('Choose one of the options.')
        return value
    if kind == 'multi_choice':
        if not isinstance(value, list) or not all(v in field['options'] for v in value):
            raise ValueError('Choose from the options.')
        picked = [o for o in field['options'] if o in value]
        return picked or None
    if kind == 'number':
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError('Enter a number.') from None
        low, high = NUMBER_RANGES.get(field['id'], (0, 1_000_000_000))
        if not low <= number <= high:
            raise ValueError(f'Enter a number between {low:,} and {high:,}.')
        return int(number) if number.is_integer() else round(number, 2)
    if kind == 'date':
        if not isinstance(value, str) or not _DATE.match(value):
            raise ValueError('Enter a date.')
        try:
            date.fromisoformat(value)
        except ValueError:
            raise ValueError('Enter a real date.') from None
        return value
    raise ValueError('This answer type is not supported.')


def validate_answers(form: dict, answers: dict | None) -> list[dict]:
    """Check the candidate's answers against the form and return the snapshot to store."""
    answers = answers if isinstance(answers, dict) else {}
    errors, snapshot = {}, []
    for field in fields_for(form):
        try:
            value = _answer(field, answers.get(field['id']))
        except ValueError as exc:
            errors[field['id']] = str(exc)
            continue
        if value is None and field['required']:
            errors[field['id']] = 'This answer is required.'
            continue
        snapshot.append({'id': field['id'], 'label': field['label'], 'type': field['type'], 'value': value})
    if errors:
        raise FormError(errors)
    return snapshot


def validate_details(details: dict | None, account_email: str) -> dict:
    """The applicant's contact details. Email is always the verified account email."""
    details = details if isinstance(details, dict) else {}
    errors = {}
    name = _clean(details.get('full_name'), 121)
    phone = _clean(details.get('phone'), 41)
    country = _clean(details.get('country'), 61)
    if len(name) < 2 or len(name) > 120:
        errors['full_name'] = 'Enter your full name.'
    if not _PHONE.match(phone or ''):
        errors['phone'] = 'Enter a phone number, e.g. +234 801 555 0101.'
    if len(country) < 2 or len(country) > 60:
        errors['country'] = 'Enter the country you live in.'
    if errors:
        raise FormError(errors)
    return {'full_name': name, 'email': account_email, 'phone': phone, 'country': country}


def prefill(user) -> dict:
    """Profile values used to fill the form in; the candidate can change them."""
    return {'full_name': user.full_name or '', 'email': user.email, 'phone': user.phone or '', 'country': user.country or '',
            'answers': {k: v for k, v in (('std_linkedin', user.linkedin_url), ('std_city', user.city)) if v}}


def save_to_profile(user, details: dict, snapshot: list[dict]) -> None:
    """Copy the applicant's contact details back to their profile when they ask."""
    user.full_name, user.phone, user.country = details['full_name'], details['phone'], details['country']
    by_id = {a['id']: a['value'] for a in snapshot}
    if by_id.get('std_linkedin'):
        user.linkedin_url = by_id['std_linkedin']
    if by_id.get('std_city'):
        user.city = by_id['std_city'][:120]


def confirmation_email(details: dict, job, snapshot: list[dict]) -> tuple[str, str]:
    """Subject and HTML confirming exactly what was sent to the employer."""
    from backend.app.services.support import _layout, _link
    first = html.escape(details['full_name'].split()[0]) if details.get('full_name') else 'there'
    rows = ''.join(
        f'<tr><td style="padding:6px 10px 6px 0;color:#64748b;vertical-align:top;">{html.escape(a["label"])}</td>'
        f'<td style="padding:6px 0;color:#0f172a;">{html.escape(_display(a["value"]))}</td></tr>' for a in snapshot)
    body = (f'<p style="color:#475569;font-size:14px;line-height:1.6;">Hi {first}, your application for '
            f'<strong>{html.escape(job.title or "the role")}</strong> at <strong>{html.escape(job.company or "the employer")}</strong> '
            f'was delivered to the employer on Baalebos, with your tailored resume.</p>'
            + (f'<p style="color:#0f172a;font-size:14px;font-weight:600;margin:16px 0 4px;">Your answers</p>'
               f'<table style="font-size:13px;border-collapse:collapse;">{rows}</table>' if rows else '')
            + f'<p style="color:#475569;font-size:14px;line-height:1.6;margin-top:16px;">The employer reviews applications '
              f'and moves them through their own stages. You can follow the status in Applications.</p>'
              f'<p style="margin:20px 0 0;"><a href="{_link("/applications")}" style="background:#059669;color:#fff;'
              f'text-decoration:none;font-weight:600;padding:11px 18px;border-radius:10px;display:inline-block;">'
              f'View my applications</a></p>')
    return f'Application sent: {job.title} at {job.company}', _layout('Your application was sent', body)


def _display(value) -> str:
    if value is None:
        return 'Not provided'
    if isinstance(value, list):
        return ', '.join(map(str, value))
    return {'yes': 'Yes', 'no': 'No'}.get(value, str(value)) if isinstance(value, str) else str(value)
