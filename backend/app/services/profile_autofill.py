"""Fill a profile from the resume kept on it (like Indeed or Jobberman).

The file is read with the same extraction as tailoring, then every fact is
checked against the file (verify_extraction), so nothing the file does not say
reaches the profile. The person reviews each item; only ticked items are saved,
existing profile values are never overwritten unless ticked, and anything the
resume does not contain is shown as "fill in yourself" rather than guessed.
"""
from __future__ import annotations

import re
from datetime import datetime

READS_PER_DAY = 3
_PHONE = re.compile(r'(\+?\d[\d ()\-.]{6,}\d)')
_LINKEDIN = re.compile(r'((?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/in/[A-Za-z0-9_\-%.]+/?)', re.I)
_EMAIL = re.compile(r'\S+@\S+')
_URL = re.compile(r'(https?://|www\.|\.(com|io|dev|org|net|xyz|me)\b|/)', re.I)


def _contact_parts(contact) -> dict:
    """Phone, LinkedIn and location from the resume's contact line."""
    text = ' | '.join(str(v) for v in contact.values()) if isinstance(contact, dict) else str(contact or '')
    found = {}
    phone = _PHONE.search(text)
    if phone and len(re.sub(r'\D', '', phone.group(1))) >= 7:
        found['phone'] = phone.group(1).strip()
    linkedin = _LINKEDIN.search(text)
    if linkedin:
        url = linkedin.group(1).rstrip('/')
        found['linkedin_url'] = url if url.lower().startswith('http') else f'https://{url}'
    # Location: what is left once email, phone and links are removed. The
    # extraction check may already have split "Lagos, Nigeria" into two pieces.
    places = []
    for part in re.split(r'\s*[|•·,]\s*|\n', text):
        part = part.strip()
        if not part or _EMAIL.search(part) or _URL.search(part) or (phone and part in phone.group(1)) \
                or not re.fullmatch(r"[^\W\d_][\w .'()-]{1,58}", part):
            continue
        places.append(part)
    if len(places) >= 2:
        found['city'], found['country'] = places[-2], places[-1]
    elif places:
        found['country'] = places[0]
    return found


def _split_dates(dates: str) -> tuple[str | None, str | None]:
    parts = re.split(r'\s*(?:–|—|-|to)\s*', str(dates or '').strip(), maxsplit=1)
    start = parts[0].strip() or None
    end = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
    return start, end


def extract(file_content: bytes, filename: str) -> dict:
    """Read the file and return only verified facts, in profile shape."""
    from backend.app.utils.ats_engine import extract_resume_data, extract_text_with_ocr, prepare_resume_text
    from backend.app.utils.resume_quality import verify_extraction
    text = prepare_resume_text(extract_text_with_ocr(file_content, filename), filename)
    data, _report = verify_extraction(extract_resume_data(text), text)
    out = {'full_name': (data.get('name') or '').strip() or None,
           'about': (data.get('summary') or '').strip() or None, **_contact_parts(data.get('contact'))}
    out['experience'] = []
    for e in data.get('experience') or []:
        if e.get('role') and e.get('company'):
            start, end = _split_dates(e.get('dates'))
            out['experience'].append({'title': e['role'].strip(), 'company': e['company'].strip(), 'start_date': start,
                                      'end_date': end, 'description': '\n'.join(f'- {b}' for b in e.get('bullets') or []) or None})
    out['education'] = [{'degree': ed['degree'].strip(), 'institution': ed['institution'].strip(),
                         'start_date': None, 'end_date': (ed.get('year') or '').strip() or None}
                        for ed in data.get('education') or [] if ed.get('degree') and ed.get('institution')]
    skills = data.get('skills') or {}
    values = [v for group in (skills.values() if isinstance(skills, dict) else [skills]) for v in (group or [])]
    seen, out['skills'] = set(), []
    for skill in values:
        name = str(skill).strip()
        if name and name.lower() not in seen and len(name) <= 60:
            seen.add(name.lower()); out['skills'].append(name)
    return out


SINGLE = [('full_name', 'Full name'), ('phone', 'Phone'), ('city', 'City'), ('country', 'Country'),
          ('linkedin_url', 'LinkedIn'), ('about', 'About you')]
NOT_READ = [('languages', 'Languages')]       # resumes are not read for these: always filled in by hand


def _key(*parts) -> str:
    return '|'.join(re.sub(r'\s+', ' ', str(p or '')).strip().lower() for p in parts)


def review_rows(user, found: dict) -> list[dict]:
    """One row per item: new (fills an empty field), keep (differs: profile wins unless ticked),
    same (nothing to do) or missing (not in the resume: fill in yourself)."""
    rows = []
    for field, label in SINGLE:
        value, current = found.get(field), getattr(user, field, None)
        if not value:
            rows.append({'key': field, 'label': label, 'status': 'missing'})
        elif not current:
            rows.append({'key': field, 'label': label, 'status': 'new', 'value': value})
        elif _key(current) == _key(value):
            rows.append({'key': field, 'label': label, 'status': 'same', 'value': value})
        else:
            rows.append({'key': field, 'label': label, 'status': 'keep', 'value': value, 'current': current})
    have_exp = {_key(e.title, e.company) for e in user.experience_entries}
    new_exp = [e for e in found.get('experience', []) if _key(e['title'], e['company']) not in have_exp]
    have_edu = {_key(e.degree, e.institution) for e in user.education_entries}
    new_edu = [e for e in found.get('education', []) if _key(e['degree'], e['institution']) not in have_edu]
    have_skill = {s.name.lower() for s in user.other_skills} | {s.name.lower() for s in user.certified_skills}
    new_skills = [s for s in found.get('skills', []) if s.lower() not in have_skill]
    for key, label, items, everything, show in (
            ('experience', 'Experience', new_exp, found.get('experience'), lambda e: f"{e['title']} at {e['company']}" + (f" ({e['start_date']} to {e['end_date'] or 'now'})" if e['start_date'] else '')),
            ('education', 'Education', new_edu, found.get('education'), lambda e: f"{e['degree']}, {e['institution']}" + (f", {e['end_date']}" if e['end_date'] else '')),
            ('skills', 'Skills', new_skills, found.get('skills'), str)):
        if not everything:
            rows.append({'key': key, 'label': label, 'status': 'missing'})
        elif not items:
            rows.append({'key': key, 'label': label, 'status': 'same', 'value': 'Already on your profile'})
        else:
            rows.append({'key': key, 'label': label, 'status': 'new', 'count': len(items), 'value': [show(i) for i in items]})
    rows += [{'key': k, 'label': label, 'status': 'missing'} for k, label in NOT_READ]
    return rows


def apply(db, user, found: dict, keys: list[str]) -> list[str]:
    """Save the ticked items. Returns the keys actually applied."""
    from backend.app.models.user import Education, Experience, OtherSkill
    applied = []
    rows = {r['key']: r for r in review_rows(user, found)}
    for key in dict.fromkeys(keys or []):
        row = rows.get(key)
        if not row or row['status'] not in ('new', 'keep'):
            continue
        if key in dict(SINGLE):
            value = found[key]
            if key == 'linkedin_url':
                from backend.app.utils.url_safety import validate_public_https_url
                try:
                    value = validate_public_https_url(value, resolve=False)
                except Exception:
                    continue
            setattr(user, key, str(value)[:2000 if key == 'about' else 255])
        elif key == 'experience':
            have = {_key(e.title, e.company) for e in user.experience_entries}
            for e in found['experience']:
                if _key(e['title'], e['company']) not in have:
                    db.add(Experience(user_id=user.id, title=e['title'][:255], company=e['company'][:255],
                                      start_date=e['start_date'], end_date=e['end_date'], description=e['description']))
        elif key == 'education':
            have = {_key(e.degree, e.institution) for e in user.education_entries}
            for e in found['education']:
                if _key(e['degree'], e['institution']) not in have:
                    db.add(Education(user_id=user.id, degree=e['degree'][:255], institution=e['institution'][:255],
                                     start_date=e['start_date'], end_date=e['end_date']))
        elif key == 'skills':
            have = {s.name.lower() for s in user.other_skills} | {s.name.lower() for s in user.certified_skills}
            for name in found['skills'][:60]:
                if name.lower() not in have:
                    db.add(OtherSkill(user_id=user.id, name=name)); have.add(name.lower())
        applied.append(key)
    return applied


def stamp(record, found: dict):
    record.extracted, record.extracted_at = found, datetime.utcnow()
