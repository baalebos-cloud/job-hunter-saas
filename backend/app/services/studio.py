"""Resume Studio: the hand-edited resume saved to the account.

The browser builds the PDF (src/studio/pdfEngine.ts); the server only keeps the
document, checks its shape and size, and offers starting points copied from
what the person already has: their profile, or a resume tailored earlier.
Copying never adds anything: a field the source does not have stays empty.
"""
from __future__ import annotations

import json
import re

PAPERS = ('A4', 'Letter')
PRESETS = ('as-is', 'cloud', 'software', 'ai')
MAX_BYTES = 120_000

TEXT = {'fullName': 120, 'headline': 300, 'location': 160, 'phone': 60, 'email': 254, 'linkedin': 300,
        'github': 300, 'portfolio': 300, 'summary': 3000, 'projectsIntro': 600}
STRING_LISTS = {'coreCompetencies': (40, 120), 'softSkills': (20, 80)}
# list key -> (max items, {field: max length}, optional list field (name, max items, max length))
OBJECT_LISTS = {
    'projects': (12, {'title': 160, 'tech': 300, 'description': 1500}, None),
    'technicalSkills': (12, {'label': 80}, ('items', 40, 80)),
    'experience': (20, {'role': 160, 'company': 160, 'location': 160, 'dates': 80}, ('bullets', 15, 700)),
    'education': (10, {'degree': 200, 'institution': 200, 'date': 80}, None),
    'certifications': (20, {'name': 200, 'issuer': 160, 'date': 80}, None),
}


class StudioError(ValueError):
    pass


def _text(value, limit: int, field: str) -> str:
    if value is None:
        return ''
    if not isinstance(value, str):
        raise StudioError(f'{field} must be text.')
    value = value.replace('\r\n', '\n').replace('\x00', '')
    if len(value) > limit:
        raise StudioError(f'{field} is longer than {limit} characters.')
    return value


def _list(value, limit: int, field: str) -> list:
    if value is None:
        return []
    if not isinstance(value, list):
        raise StudioError(f'{field} must be a list.')
    if len(value) > limit:
        raise StudioError(f'{field} has more than {limit} entries.')
    return value


def validate(data) -> dict:
    """Return a clean ResumeData dict or raise StudioError. Unknown keys are dropped."""
    if not isinstance(data, dict):
        raise StudioError('The resume must be an object.')
    out = {key: _text(data.get(key), limit, key) for key, limit in TEXT.items()}
    for key, (count, length) in STRING_LISTS.items():
        out[key] = [_text(v, length, key) for v in _list(data.get(key), count, key)]
    for key, (count, fields, nested) in OBJECT_LISTS.items():
        rows = []
        for row in _list(data.get(key), count, key):
            if not isinstance(row, dict):
                raise StudioError(f'Each {key} entry must be an object.')
            clean = {name: _text(row.get(name), limit, f'{key}.{name}') for name, limit in fields.items()}
            if nested:
                name, n, limit = nested
                clean[name] = [_text(v, limit, f'{key}.{name}') for v in _list(row.get(name), n, f'{key}.{name}')]
            rows.append(clean)
        out[key] = rows
    if len(json.dumps(out, ensure_ascii=False).encode()) > MAX_BYTES:
        raise StudioError('The resume is too large to save.')
    return out


def empty() -> dict:
    return validate({})


def _fit(value, key: str) -> str:
    return str(value or '').strip()[:TEXT[key]]


_EMAIL = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
_PHONE = re.compile(r'^\+?[\d ()\-.]{7,}$')


def _split_contact(contact) -> dict:
    """Sort the pieces of a tailored resume's contact line into Studio fields."""
    parts = contact.values() if isinstance(contact, dict) else re.split(r'\s*\|\s*', str(contact or ''))
    found, places = {}, []
    for part in (str(p).strip() for p in parts):
        if not part:
            continue
        low = part.lower()
        if _EMAIL.match(part):
            found.setdefault('email', part)
        elif 'linkedin.com' in low:
            found.setdefault('linkedin', part)
        elif 'github.com' in low:
            found.setdefault('github', part)
        elif low.startswith(('http://', 'https://', 'www.')) or re.search(r'\.[a-z]{2,}(/|$)', low):
            found.setdefault('portfolio', part)
        elif _PHONE.match(part) and sum(c.isdigit() for c in part) >= 7:
            found.setdefault('phone', part)
        else:
            places.append(part)
    if places:
        found['location'] = ', '.join(places)
    return {k: _fit(v, k) for k, v in found.items()}


def from_tailored(tailored: dict) -> dict:
    """A resume tailored earlier (Resume.parsed_data), in Studio shape."""
    if not isinstance(tailored, dict):
        return empty()
    skills = tailored.get('skills') or {}
    groups = skills.items() if isinstance(skills, dict) else [('Skills', skills)]
    certs = []
    for c in tailored.get('certifications') or []:
        if isinstance(c, dict):
            certs.append({'name': str(c.get('name') or ''), 'issuer': str(c.get('issuer') or ''), 'date': str(c.get('date') or c.get('year') or '')})
        elif str(c).strip():
            certs.append({'name': str(c).strip(), 'issuer': '', 'date': ''})
    data = {
        'fullName': _fit(tailored.get('name'), 'fullName'),
        'headline': _fit(tailored.get('title'), 'headline'),
        **_split_contact(tailored.get('contact')),
        'summary': _fit(tailored.get('summary'), 'summary'),
        'technicalSkills': [{'label': str(label or 'Skills')[:80], 'items': [str(i)[:80] for i in (items or []) if str(i).strip()][:40]}
                            for label, items in list(groups)[:12] if items],
        'experience': [{'role': str(e.get('role') or ''), 'company': str(e.get('company') or ''),
                        'location': str(e.get('location') or ''), 'dates': str(e.get('dates') or ''),
                        'bullets': [str(b) for b in e.get('bullets') or [] if str(b).strip()][:15]}
                       for e in (tailored.get('experience') or [])[:20] if isinstance(e, dict)],
        'projects': [{'title': ' — '.join(p for p in (str(x.get('title') or ''), str(x.get('subtitle') or '')) if p),
                      'tech': str(x.get('tech') or ''), 'description': ' '.join(str(b) for b in x.get('bullets') or [])}
                     for x in (tailored.get('projects') or [])[:12] if isinstance(x, dict)],
        'education': [{'degree': str(s.get('degree') or ''), 'institution': str(s.get('institution') or ''),
                       'date': str(s.get('year') or s.get('date') or '')}
                      for s in (tailored.get('education') or [])[:10] if isinstance(s, dict)],
        'certifications': certs[:20],
    }
    return validate(_truncate(data))


def from_profile(user) -> dict:
    """The person's profile, in Studio shape."""
    def dates(e):
        start, end = (e.start_date or '').strip(), (e.end_date or '').strip()
        return f'{start} – {end or "Present"}' if start else end
    skills = [s.name for s in user.certified_skills] + [s.name for s in user.other_skills]
    seen, unique = set(), []
    for s in skills:
        if s and s.lower() not in seen:
            seen.add(s.lower()); unique.append(s)
    data = {
        'fullName': _fit(user.full_name, 'fullName'),
        'headline': _fit(user.career_track, 'headline'),
        'location': _fit(', '.join(p for p in (user.city, user.country) if p), 'location'),
        'phone': _fit(user.phone, 'phone'),
        'email': _fit(user.email, 'email'),
        'linkedin': _fit(user.linkedin_url, 'linkedin'),
        'summary': _fit(user.about, 'summary'),
        'technicalSkills': [{'label': 'Skills', 'items': unique[:40]}] if unique else [],
        'experience': [{'role': e.title or '', 'company': e.company or '', 'location': '', 'dates': dates(e),
                        'bullets': [line.lstrip('-•* ').strip() for line in (e.description or '').splitlines() if line.strip()][:15]}
                       for e in list(user.experience_entries)[:20]],
        'education': [{'degree': e.degree or '', 'institution': e.institution or '', 'date': (e.end_date or e.start_date or '')}
                      for e in list(user.education_entries)[:10]],
    }
    return validate(_truncate(data))


def _truncate(data: dict) -> dict:
    """Cut copied values to the Studio limits (copies are never rejected for length)."""
    for key, (_, fields, nested) in OBJECT_LISTS.items():
        for row in data.get(key, []):
            for name, limit in fields.items():
                row[name] = str(row.get(name) or '')[:limit]
            if nested:
                name, n, limit = nested
                row[name] = [str(v)[:limit] for v in row.get(name, [])][:n]
    return data
