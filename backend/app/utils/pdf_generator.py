"""ATS-friendly, single-column resume export.

Rules enforced here:
* Zero watermarks/branding (hard invariant): every field passes through
  ``strip_watermarks_and_branding``; no footer, page counter, watermark layer,
  producer/creator tag or generator comment is written. ``improvements`` and
  ``score`` are accepted for backwards compatibility and ignored.
* No tables, images or colour-coded meaning (one accent colour for the name
  and headings only). Text is selectable and uses embedded TTFs: Carlito,
  or DejaVu Sans for the whole document when Carlito lacks a glyph the text
  needs, with Noto/WenQuanYi fallbacks for other scripts. Real text bullets;
  dates sit right-aligned on the entry line as a separate text run.
* Section order: Professional Summary, Core Skills, Professional Experience,
  Selected Projects, Certifications, Education, Additional Information
  (empty sections omitted).
* Page size follows the candidate's region: US Letter for US/CA, A4 otherwise.
* Strictly one page: standard (10pt) -> balanced (9.5pt) -> compact (9pt)
  profiles, then secondary content is condensed. Employers, titles, dates,
  degrees and certifications are never removed. Verified with pypdf.
"""
from __future__ import annotations

import contextvars
import copy
import os
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate

FONT_DIRECTORY = Path(__file__).resolve().parents[1] / 'assets' / 'fonts'
# Carlito is metric-compatible with Calibri. DejaVu Sans covers far more
# Latin (e.g. Yoruba dot-below letters), so a document Carlito cannot fully
# draw uses DejaVu throughout rather than mixing fonts inside names.
FONT_FAMILIES = {
    'Carlito': ('Carlito-Regular.ttf', 'Carlito-Bold.ttf', 'Carlito-Italic.ttf', 'Carlito-BoldItalic.ttf'),
    'DejaVuSans': ('DejaVuSans.ttf', 'DejaVuSans-Bold.ttf', 'DejaVuSans-Oblique.ttf', 'DejaVuSans-BoldOblique.ttf'),
}
PRIMARY_FONT, WIDE_LATIN_FONT = 'Carlito', 'DejaVuSans'
for _family, (_regular, _bold, _italic, _bold_italic) in FONT_FAMILIES.items():
    for _suffix, _file in (('', _regular), ('-Bold', _bold), ('-Italic', _italic), ('-BoldItalic', _bold_italic)):
        pdfmetrics.registerFont(TTFont(_family + _suffix, str(FONT_DIRECTORY / _file)))
    pdfmetrics.registerFontFamily(_family, normal=_family, bold=f'{_family}-Bold',
                                  italic=f'{_family}-Italic', boldItalic=f'{_family}-BoldItalic')
# The base family of the document being rendered; fallbacks are relative to it.
_DOCUMENT_FONT = contextvars.ContextVar('resume_document_font', default=PRIMARY_FONT)
# Main language of the resume being rendered (PDF /Lang; right alignment for Arabic/Hebrew).
_DOCUMENT_LANG = contextvars.ContextVar('resume_document_lang', default='en')

ACCENT_COLOR = colors.HexColor('#1F4E79')   # name, headings and rules only; carries no meaning
TEXT_COLOR = colors.HexColor('#1A1A1A')
MUTED_COLOR = colors.HexColor('#555555')
MUTED_HEX = '#555555'

REGIONS = ('US', 'CA', 'UK', 'EU', 'NG', 'OTHER')
LETTER_REGIONS = {'US', 'CA'}
# Where employers expect one page by default; elsewhere a resume may use two.
ONE_PAGE_REGIONS = {'US', 'CA'}
# Personal details that US, Canadian and UK conventions (and anti-discrimination
# guidance) exclude. They are never added; for these regions they are also
# dropped when the source resume contains them. Elsewhere they are kept and
# the export says so in its warnings.
STRIP_PERSONAL_REGIONS = {'US', 'CA', 'UK'}
PERSONAL_DETAIL_PATTERN = re.compile(
    r'\b(date of birth|d\.?o\.?b\.?|birth ?date|age|marital status|religion|gender|sex|'
    r'state of origin|lga|local government|nationality|next of kin)\b\s*[:\-]', re.IGNORECASE)

_EU_COUNTRIES = {
    'austria', 'belgium', 'bulgaria', 'croatia', 'cyprus', 'czechia', 'czech republic', 'denmark', 'estonia',
    'finland', 'france', 'germany', 'greece', 'hungary', 'ireland', 'italy', 'latvia', 'lithuania', 'luxembourg',
    'malta', 'netherlands', 'poland', 'portugal', 'romania', 'slovakia', 'slovenia', 'spain', 'sweden',
    'at', 'be', 'bg', 'hr', 'cy', 'cz', 'dk', 'ee', 'fi', 'fr', 'de', 'gr', 'hu', 'ie', 'it', 'lv', 'lt', 'lu',
    'mt', 'nl', 'pl', 'pt', 'ro', 'sk', 'si', 'es', 'se', 'eu', 'european union'}
_COUNTRY_REGION = {
    'us': 'US', 'usa': 'US', 'u.s.': 'US', 'u.s.a.': 'US', 'united states': 'US', 'united states of america': 'US', 'america': 'US',
    'ca': 'CA', 'canada': 'CA',
    'uk': 'UK', 'gb': 'UK', 'u.k.': 'UK', 'united kingdom': 'UK', 'great britain': 'UK', 'england': 'UK',
    'scotland': 'UK', 'wales': 'UK', 'northern ireland': 'UK',
    'ng': 'NG', 'nigeria': 'NG',
}

MONTHS = {m.lower(): m[:3] for m in (
    'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December')}
MONTHS.update({'sept': 'Sep'})
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})


class ResumeExportError(ValueError):
    """Raised when there is not enough real candidate data to export."""


def resolve_region(region: str | None = None, country: str | None = None) -> str:
    """Map an explicit region code or a free-text country to a supported region."""
    if region:
        code = str(region).strip().upper()
        if code in REGIONS:
            return code
        if code == 'GB':
            return 'UK'
    key = re.sub(r'\s+', ' ', str(country or '')).strip().casefold()
    if not key:
        return 'OTHER'
    if key in _COUNTRY_REGION:
        return _COUNTRY_REGION[key]
    if key in _EU_COUNTRIES:
        return 'EU'
    return 'OTHER'


def page_size_for_region(region: str | None) -> tuple[float, float]:
    return LETTER if resolve_region(region) in LETTER_REGIONS else A4


def resolve_max_pages(region: str | None, requested=None) -> int | str:
    """1, 2 or 'auto' (one page when it fits, otherwise up to two).

    Default: 1 for US/Canada, 'auto' elsewhere. An explicit 1 or 2 always wins."""
    value = str(requested).strip().lower() if requested is not None else ''
    if value in ('1', '2'):
        return int(value)
    if value == 'auto':
        return 'auto'
    if value:
        raise ResumeExportError('Page length must be 1, 2 or auto.')
    return 1 if resolve_region(region) in ONE_PAGE_REGIONS else 'auto'


# ── Normalisation ─────────────────────────────────────────────────────────────

_CONTROL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b-\u200f\u202a-\u202e\u2060\ufeff]')
_BULLET_PREFIX = re.compile(r'^\s*(?:[\-\*\u2022\u2023\u25aa\u25cf\u25e6\u2043\u2219\u00b7\u27a2\u2794\u2192\uf0b7\uf0a7]+|\d+[.)])\s*')


def _text(value) -> str:
    """Coerce any scalar/collection into a clean single string."""
    if value is None or isinstance(value, bool):
        return ''
    if isinstance(value, (list, tuple, set)):
        return ', '.join(t for t in (_text(v) for v in value) if t)
    if isinstance(value, dict):
        return ', '.join(t for t in (_text(v) for v in value.values()) if t)
    text = unicodedata.normalize('NFC', str(value))
    text = _CONTROL.sub('', text)
    return re.sub(r'[ \t\r\f\v]+', ' ', text).strip()


def _lines(value) -> list[str]:
    """Coerce a list, string (one item per line) or dict into a list of strings."""
    if value is None:
        return []
    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, str):
        value = value.splitlines()
    if not isinstance(value, (list, tuple)):
        value = [value]
    items = []
    for item in value:
        text = _text(item)
        text = _BULLET_PREFIX.sub('', text).strip()
        if text:
            items.append(text)
    return items


def _unique(items):
    seen, out = set(), []
    for item in items:
        key = item.casefold()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _pick(entry: dict, *keys) -> str:
    for key in keys:
        if key in entry and _text(entry[key]):
            return _text(entry[key])
    return ''


def normalize_dates(value) -> str:
    """Normalise date ranges to "Mon YYYY - Mon YYYY" / "Present" without
    inventing anything: unrecognised text is returned unchanged (cleaned)."""
    text = _text(value)
    if not text:
        return ''
    text = re.sub(r'\s*(?:[\u2010-\u2015\u2212]|\bto\b|\buntil\b|\btill\b)\s*', ' - ', text, flags=re.IGNORECASE)
    # ASCII hyphens only separate a range ("2019-2021", "Jan 2020 -Mar 2021"),
    # never numeric dates such as "2020-01".
    text = re.sub(r'(?:(?<=\d{4})\s*|\s+)-{1,2}\s*(?=[A-Za-z]{3,}|\d{4})', ' - ', text)

    def month(match):
        word = match.group(0)
        return MONTHS.get(word.lower().rstrip('.'), word)
    text = re.sub(r'\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|'
                  r'sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?(?=\s*,?\s*\d{4}\b)',
                  month, text, flags=re.IGNORECASE)
    text = re.sub(r'\b([A-Z][a-z]{2}),\s*(\d{4})\b', r'\1 \2', text)
    text = re.sub(r'\b(present|current|currently|now|date|ongoing)\b', 'Present', text, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', text).strip(' -')


def _contact(value) -> str:
    if isinstance(value, dict):
        order = ('email', 'phone', 'location', 'city', 'country', 'linkedin', 'github', 'portfolio', 'website', 'url')
        parts = [_text(value[k]) for k in order if k in value] + [
            _text(v) for k, v in value.items() if k not in order]
    elif isinstance(value, (list, tuple)):
        parts = [_text(v) for v in value]
    else:
        parts = re.split(r'\s*(?:\n|\||\u2022|\u00b7|\u25cf|\u2016)\s*', unicodedata.normalize('NFC', str(value or '')))
        parts = [_text(p) for p in parts]
    return ' | '.join(_unique([p for p in parts if p]))


def _skills(value) -> dict[str, list[str]]:
    if isinstance(value, dict):
        groups = {}
        for category, items in value.items():
            name = _text(category) or 'Skills'
            values = _split_skills(items)
            if values:
                groups.setdefault(name, [])
                groups[name] = _unique(groups[name] + values)
        return groups
    values = _split_skills(value)
    return {'Skills': values} if values else {}


def _split_skills(value) -> list[str]:
    if isinstance(value, str):
        value = re.split(r'\s*[,;\n\u2022|]\s*', value)
    return _unique(_lines(value))


def _experience(value) -> list[dict]:
    entries = []
    for item in value if isinstance(value, list) else ([value] if value else []):
        if isinstance(item, str):
            if _text(item):
                entries.append({'role': _text(item), 'company': '', 'location': '', 'dates': '', 'bullets': [], 'environment': ''})
            continue
        if not isinstance(item, dict):
            continue
        dates = _pick(item, 'dates', 'date', 'duration', 'period')
        if not dates and (item.get('start_date') or item.get('end_date')):
            dates = ' - '.join(p for p in (_text(item.get('start_date')), _text(item.get('end_date')) or 'Present') if p)
        entry = {
            'role': _pick(item, 'role', 'title', 'position', 'job_title'),
            'company': _pick(item, 'company', 'employer', 'organization', 'organisation'),
            'location': _pick(item, 'location', 'city'),
            'dates': normalize_dates(dates),
            'bullets': _lines(item.get('bullets') or item.get('responsibilities') or item.get('achievements') or item.get('description')),
            'environment': _pick(item, 'environment', 'tools', 'technologies', 'tech'),
        }
        if any(entry[k] for k in ('role', 'company', 'bullets')):
            entries.append(entry)
    return entries


def _projects(value) -> list[dict]:
    entries = []
    for item in value if isinstance(value, list) else ([value] if value else []):
        if isinstance(item, str):
            if _text(item):
                entries.append({'title': _text(item), 'subtitle': '', 'tech': '', 'bullets': []})
            continue
        if not isinstance(item, dict):
            continue
        entry = {'title': _pick(item, 'title', 'name'),
                 'subtitle': _pick(item, 'subtitle', 'tagline', 'summary'),
                 'tech': _pick(item, 'tech', 'technologies', 'stack', 'tools'),
                 'bullets': _lines(item.get('bullets') or item.get('description'))}
        if entry['title'] or entry['bullets']:
            entries.append(entry)
    return entries


def _education(value) -> list[dict]:
    entries = []
    for item in value if isinstance(value, list) else ([value] if value else []):
        if isinstance(item, str):
            if _text(item):
                entries.append({'degree': _text(item), 'institution': '', 'location': '', 'year': ''})
            continue
        if not isinstance(item, dict):
            continue
        entry = {'degree': _pick(item, 'degree', 'qualification', 'title'),
                 'institution': _pick(item, 'institution', 'school', 'university'),
                 'location': _pick(item, 'location'),
                 'year': normalize_dates(_pick(item, 'year', 'dates', 'date', 'graduation'))}
        if entry['degree'] or entry['institution']:
            entries.append(entry)
    return entries


def _certifications(value) -> list[str]:
    certs = []
    for item in value if isinstance(value, list) else _lines(value):
        if isinstance(item, dict):
            text = ' | '.join(p for p in (_pick(item, 'name', 'title'), _pick(item, 'issuer', 'organization'),
                                          _pick(item, 'year', 'date', 'status')) if p)
        else:
            text = _BULLET_PREFIX.sub('', _text(item))
        if text:
            certs.append(text)
    return _unique(certs)


def normalize_resume_data(raw) -> dict:
    """Return a fully-typed resume dict from untrusted (LLM) JSON.

    Tolerates missing keys, wrong types, skills as a list/dict/string and
    strings where lists are expected. Never adds content that is not present.
    """
    raw = raw if isinstance(raw, dict) else {}
    return {
        'name': _text(raw.get('name') or raw.get('full_name')),
        'title': _text(raw.get('title') or raw.get('headline')),
        'contact': _contact(raw.get('contact') or {k: raw[k] for k in ('email', 'phone', 'location', 'linkedin') if raw.get(k)}),
        'summary': _text(raw.get('summary') or raw.get('profile') or raw.get('objective')),
        'experience': _experience(raw.get('experience') or raw.get('work_experience')),
        'skills': _skills(raw.get('skills')),
        'education': _education(raw.get('education')),
        'certifications': _certifications(raw.get('certifications')),
        'projects': _projects(raw.get('projects')),
        'additional_information': '\n'.join(_lines(raw.get('additional_information'))),
    }


def has_exportable_content(data: dict) -> bool:
    return bool(data.get('name')) and any(data.get(k) for k in ('summary', 'experience', 'skills', 'education', 'projects'))


_PHOTO_LINE = re.compile(r'\b(photo|photograph|headshot|passport picture)\b', re.IGNORECASE)


def personal_details(data: dict) -> list[str]:
    """Personal-detail labels present in the contact line or additional information."""
    found = []
    text = '\n'.join([data.get('additional_information', ''), *data.get('contact', '').split(' | ')])
    for match in PERSONAL_DETAIL_PATTERN.finditer(text):
        label = match.group(1).strip().lower()
        if label not in found:
            found.append(label)
    if _PHOTO_LINE.search(data.get('additional_information', '')) and 'photo' not in found:
        found.append('photo')
    return found


def apply_region_rules(data: dict, region: str) -> dict:
    """US/CA/UK convention: no DOB, marital status, photo or similar details."""
    if resolve_region(region) not in STRIP_PERSONAL_REGIONS:
        return data
    lines = [line for line in data.get('additional_information', '').splitlines()
             if not PERSONAL_DETAIL_PATTERN.search(line) and not _PHOTO_LINE.search(line)]
    contact = ' | '.join(p for p in data.get('contact', '').split(' | ') if not PERSONAL_DETAIL_PATTERN.search(p))
    return {**data, 'additional_information': '\n'.join(lines), 'contact': contact}


def merge_confirmed_keywords(data: dict, keywords) -> dict:
    """Add skills the candidate explicitly confirmed. Nothing else is added."""
    data = normalize_resume_data(data)
    existing = {s.casefold() for values in data['skills'].values() for s in values}
    confirmed = [k for k in _unique(_lines(keywords)) if k.casefold() not in existing]
    if not confirmed:
        return data
    skills = {category: list(values) for category, values in data['skills'].items()}
    if list(skills) == ['Skills'] or not skills:
        skills['Skills'] = skills.get('Skills', []) + confirmed
        return {**data, 'skills': skills}
    for keyword in confirmed:
        skills.setdefault(_category_for(keyword, skills), []).append(keyword)
    return {**data, 'skills': skills}


def _category_for(keyword: str, skills: dict) -> str:
    """The resume's own skill group a confirmed keyword belongs in.

    The keyword's taxonomy category (Cloud, CI/CD, Finance & Accounting...) is
    matched to the resume group that already holds skills of that category, or
    to a group with that name; otherwise a group named after the category is
    added. Keywords the taxonomy does not know go to "Additional Skills"."""
    from backend.app.utils.skill_terms import SKILL_CATEGORIES, find_terms
    terms = find_terms(keyword)
    category = SKILL_CATEGORIES.get(terms[0]) if terms else None
    if not category:
        return 'Additional Skills'
    for group, values in skills.items():
        if group.casefold() == category.casefold():
            return group
    for group, values in skills.items():
        if any(SKILL_CATEGORIES.get(term) == category for value in values for term in find_terms(value)):
            return group
    return category


# ── Rendering ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Layout:
    name: str
    body: float
    leading: float
    margin: float
    title: float
    section_gap: float
    entry_gap: float


# Progressive profiles: content is fitted by layout first, trimmed last.
LAYOUTS = (
    Layout('standard', body=10, leading=12.4, margin=36, title=16, section_gap=6, entry_gap=3),
    Layout('balanced', body=9.5, leading=11.6, margin=28, title=15, section_gap=4.5, entry_gap=2),
    Layout('compact', body=9, leading=10.8, margin=24, title=14, section_gap=3.5, entry_gap=1.5),
)
MIN_BODY_FONT = 9
MAX_PAGES = 2            # the most any export may use; 1 is the default for US/CA


@dataclass
class ExportResult:
    pdf: bytes
    pages: int
    page_size: str
    region: str
    layout: str
    font: str = PRIMARY_FONT
    condensed: bool = False
    condensed_items: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    max_pages: int | str = 1
    lang: str = 'en'
    content: dict = field(default_factory=dict)   # what was rendered (after region rules and condensing)

    def info(self) -> dict:
        return {'pages': self.pages, 'page_size': self.page_size, 'region': self.region, 'layout': self.layout,
                'font': self.font, 'condensed': self.condensed, 'condensed_items': list(self.condensed_items),
                'warnings': list(self.warnings), 'max_pages': self.max_pages, 'lang': self.lang}


# ── Unicode font fallback ────────────────────────────────────────────────────
# DejaVu Sans covers Latin (incl. Yoruba), Greek and Cyrillic. Other scripts
# fall back to Noto / WenQuanYi fonts installed in the image (Dockerfile:
# fonts-noto-core, fonts-wqy-zenhei). Extra directories: RESUME_FONT_DIRS.
FALLBACK_FONTS = (
    ('ResumeNoto', 'NotoSans-Regular.ttf', None),
    ('ResumeArabic', 'NotoSansArabic-Regular.ttf', None),
    ('ResumeHebrew', 'NotoSansHebrew-Regular.ttf', None),
    ('ResumeDevanagari', 'NotoSansDevanagari-Regular.ttf', None),
    ('ResumeBengali', 'NotoSansBengali-Regular.ttf', None),
    ('ResumeTamil', 'NotoSansTamil-Regular.ttf', None),
    ('ResumeThai', 'NotoSansThai-Regular.ttf', None),
    ('ResumeEthiopic', 'NotoSansEthiopic-Regular.ttf', None),
    ('ResumeArmenian', 'NotoSansArmenian-Regular.ttf', None),
    ('ResumeGeorgian', 'NotoSansGeorgian-Regular.ttf', None),
    ('ResumeCJK', 'wqy-zenhei.ttc', 0),
)
FONT_SEARCH_DIRS = [FONT_DIRECTORY, Path('/usr/share/fonts/truetype/noto'), Path('/usr/share/fonts/truetype/wqy'),
                    Path('/usr/share/fonts/truetype/noto-cjk')]
_RTL = re.compile(r'[\u0590-\u08ff\ufb1d-\ufdff\ufe70-\ufefc]')


def _font_dirs():
    extra = [Path(p) for p in os.getenv('RESUME_FONT_DIRS', '').split(os.pathsep) if p]
    return extra + FONT_SEARCH_DIRS


@lru_cache(maxsize=None)
def _coverage(family: str) -> frozenset:
    return frozenset(pdfmetrics.getFont(family).face.charWidths)


def choose_font(data: dict) -> str:
    """Carlito unless it lacks characters DejaVu Sans can draw; then DejaVu."""
    text = _all_text(data)
    lacking = {ord(c) for c in text if ord(c) >= 0x80 and not c.isspace()} - _coverage(PRIMARY_FONT)
    return WIDE_LATIN_FONT if lacking & _coverage(WIDE_LATIN_FONT) else PRIMARY_FONT


def _all_text(data: dict) -> str:
    parts = [data['name'], data['title'], data['contact'], data['summary'], data['additional_information']]
    parts += [item for category, values in data['skills'].items() for item in (category, ' '.join(values))]
    for section in ('experience', 'projects', 'education'):
        parts += [str(v) for entry in data[section] for v in entry.values()]
    return ' '.join(parts + data['certifications'])


@lru_cache(maxsize=None)
def _fallback(name: str):
    """Register a fallback font on first use; returns its coverage or None."""
    for font_name, filename, index in FALLBACK_FONTS:
        if font_name != name:
            continue
        for directory in _font_dirs():
            path = directory / filename
            if path.is_file():
                try:
                    font = TTFont(font_name, str(path), subfontIndex=index) if index is not None else TTFont(font_name, str(path))
                    pdfmetrics.registerFont(font)
                    return frozenset(font.face.charWidths)
                except Exception:  # unreadable/CFF font: try the next location
                    continue
    return None


def _font_for(char: str):
    """Return None for the primary font, a fallback font name, or '' if no
    installed font can render the character."""
    code = ord(char)
    if code < 0x80 or code in _coverage(_DOCUMENT_FONT.get()):
        return None
    for font_name, _, _ in FALLBACK_FONTS:
        coverage = _fallback(font_name)
        if coverage and code in coverage:
            return font_name
    return ''


def _visual_order(run: str) -> str:
    """Shape and reorder right-to-left runs (Arabic/Hebrew) for ReportLab."""
    if not _RTL.search(run):
        return run
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(run))
    except Exception:
        return run


def _clean(value) -> str:
    """Escape candidate text for ReportLab markup, switching to fallback fonts
    for scripts the primary font cannot render."""
    text = _text(value)
    if all(ord(c) < 0x80 for c in text):
        return escape(text)
    runs, current, buffer = [], None, []
    for char in text:
        font = current if unicodedata.combining(char) and buffer else _font_for(char)
        font = None if font == '' else font
        if font != current and buffer:
            runs.append((current, ''.join(buffer)))
            buffer = []
        current = font
        buffer.append(char)
    if buffer:
        runs.append((current, ''.join(buffer)))
    out = []
    for font, run in runs:
        piece = escape(_visual_order(run) if font else run)
        out.append(f'<font name="{font}">{piece}</font>' if font else piece)
    return ''.join(out)


def _unsupported_characters(data: dict) -> list[str]:
    text = ' '.join([data['name'], data['title'], data['contact'], data['summary'], data['additional_information']]
                    + [str(v) for e in data['experience'] for v in e.values()]
                    + [str(v) for e in data['education'] for v in e.values()])
    return sorted({c for c in text if ord(c) > 0x7f and not unicodedata.combining(c)
                   and unicodedata.category(c)[0] in 'LNPS' and _font_for(c) == ''})


class SectionHeading(Flowable):
    """Bold accent-coloured caps over a thin rule, kept with the content that follows."""

    def __init__(self, text: str, font: str, size: float, space_before: float):
        super().__init__()
        self.text, self.font, self.size = text.upper(), font, size
        self.keepWithNext = 1
        self.spaceBefore, self.spaceAfter = space_before, 3

    def wrap(self, available_width, available_height):
        self.width = available_width
        return available_width, self.size + 4

    def draw(self):
        canvas = self.canv
        canvas.setFillColor(ACCENT_COLOR)
        canvas.setFont(self.font, self.size)
        canvas.drawString(0, 4.5, self.text)
        canvas.setStrokeColor(ACCENT_COLOR)
        canvas.setLineWidth(0.8)
        canvas.line(0, 1.5, self.width, 1.5)


class EntryLine(Flowable):
    """Entry text on the left, dates right-aligned on the same first line.

    Drawn as two text runs, not a table, so ATS parsers read it in order.
    """

    def __init__(self, left_markup: str, right: str, style: ParagraphStyle, right_font: str, keep_with_next: bool):
        super().__init__()
        self.left_markup, self.right, self.style, self.right_font = left_markup, right, style, right_font
        self.keepWithNext = 1 if keep_with_next else 0
        self.spaceBefore = style.spaceBefore

    def wrap(self, available_width, available_height):
        self.width = available_width
        right_width = stringWidth(self.right, self.right_font, self.style.fontSize) if self.right else 0
        self.paragraph = Paragraph(self.left_markup, self.style)
        _, self.height = self.paragraph.wrap(available_width - (right_width + 12 if self.right else 0), available_height)
        return available_width, self.height

    def draw(self):
        self.paragraph.drawOn(self.canv, 0, 0)
        if self.right:
            ascent = pdfmetrics.getAscentDescent(self.style.fontName, self.style.fontSize)[0]
            self.canv.setFont(self.right_font, self.style.fontSize)
            self.canv.setFillColor(MUTED_COLOR)
            self.canv.drawRightString(self.width, self.height - ascent, self.right)


def _styles(layout: Layout, font: str) -> dict[str, ParagraphStyle]:
    # splitLongWords + uriWasteReduce wrap long URLs/tokens without inserting
    # characters into the extractable text (which would corrupt ATS parsing).
    bold, italic = f'{font}-Bold', f'{font}-Italic'
    base = dict(fontName=font, fontSize=layout.body, leading=layout.leading, textColor=TEXT_COLOR,
                splitLongWords=1, uriWasteReduce=0.3)
    from backend.app.utils.language import RTL_LANGS
    if _DOCUMENT_LANG.get() in RTL_LANGS:
        base['alignment'] = TA_RIGHT     # right-to-left resumes read from the right margin
    return {
        'name': ParagraphStyle('Name', **{**base, 'fontName': bold, 'fontSize': layout.title,
                                          'leading': layout.title * 1.2, 'textColor': ACCENT_COLOR,
                                          'alignment': TA_CENTER}),
        'title': ParagraphStyle('Title', **{**base, 'textColor': MUTED_COLOR, 'alignment': TA_CENTER}),
        'contact': ParagraphStyle('Contact', **{**base, 'textColor': MUTED_COLOR, 'alignment': TA_CENTER}),
        'body': ParagraphStyle('Body', **base),
        'skill': ParagraphStyle('Skill', **{**base, 'spaceAfter': 1}),
        'entry': ParagraphStyle('Entry', **{**base, 'fontName': bold, 'spaceBefore': layout.entry_gap + 2}),
        'meta': ParagraphStyle('Meta', **{**base, 'fontName': italic, 'textColor': MUTED_COLOR, 'spaceAfter': 1}),
        'bullet': ParagraphStyle('Bullet', **{**base, 'leftIndent': 14, 'bulletIndent': 4, 'spaceAfter': 1,
                                              'bulletFontName': font, 'bulletFontSize': layout.body}),
    }


def _bullet_markup(text: str) -> str:
    """Bold a short lead-in written as "Label: sentence" (at most six words, no full stop)."""
    head, sep, tail = text.partition(': ')
    if sep and tail and 2 <= len(head) <= 48 and len(head.split()) <= 6 and '.' not in head:
        return f'<b>{_clean(head)}:</b> {_clean(tail)}'
    return _clean(text)


def _muted(text: str, font: str) -> str:
    """Regular-weight muted text inside a bold entry line."""
    return f"<font name='{font}' color='{MUTED_HEX}'>{_clean(text)}</font>"


def _tech_line(value: str) -> str:
    return ' · '.join(_split_skills(value))


def _story(data: dict, layout: Layout, font: str) -> list:
    s = _styles(layout, font)
    story = []

    def heading(title):
        story.append(SectionHeading(title, f'{font}-Bold', layout.body, layout.section_gap + 3))

    def entry(primary, secondary, right, keep_with_next):
        # Dates in a script the base font lacks stay in the paragraph, which
        # handles font fallback; plain dates are drawn right-aligned.
        if right and any(_font_for(c) for c in right):
            secondary, right = ' · '.join(p for p in (secondary, right) if p), ''
        left = f'<b>{_clean(primary)}</b>' if primary else ''
        if secondary:
            left += ('  ' + _muted('|  ' + secondary, font)) if left else _muted(secondary, font)
        if left or right:
            story.append(EntryLine(left, right, s['entry'], f'{font}-Italic', keep_with_next))

    def bullets(items, labels=True):
        for item in items:
            markup = _bullet_markup(item) if labels else _clean(item)
            story.append(Paragraph(markup, s['bullet'], bulletText='•'))

    story.append(Paragraph(_clean(data['name']), s['name']))
    if data['title']:
        story.append(Paragraph(_clean(data['title']), s['title']))
    if data['contact']:
        story.append(Paragraph(_clean(data['contact']), s['contact']))

    if data['summary']:
        heading('Professional Summary')
        story.append(Paragraph(_clean(data['summary']), s['body']))
    if data['skills']:
        heading('Core Skills')
        for category, values in data['skills'].items():
            line = _clean(', '.join(values))
            if not (category == 'Skills' and len(data['skills']) == 1):
                line = f'<b>{_clean(category)}:</b> ' + line
            story.append(Paragraph(line, s['skill']))
    if data['experience']:
        heading('Professional Experience')
        for job in data['experience']:
            organisation = ' · '.join(p for p in (job['company'], job['location']) if p)
            entry(job['role'], organisation, job['dates'], bool(job['bullets'] or job['environment']))
            bullets(job['bullets'])
            if job['environment']:
                story.append(Paragraph('<b>Tools:</b> ' + _clean(_tech_line(job['environment'])), s['body']))
    if data['projects']:
        heading('Selected Projects')
        for project in data['projects']:
            entry(project['title'], project['subtitle'], '', True)
            if project['tech']:
                story.append(Paragraph(_clean(_tech_line(project['tech'])), s['meta']))
            bullets(project['bullets'])
    if data['certifications']:
        heading('Certifications')
        bullets(data['certifications'], labels=False)  # "AWS Educate: ..." is a name, not a label
    if data['education']:
        heading('Education')
        for edu in data['education']:
            entry(edu['degree'], ' · '.join(p for p in (edu['institution'], edu['location']) if p), edu['year'], False)
    if data['additional_information']:
        heading('Additional Information')
        for line in data['additional_information'].splitlines():
            story.append(Paragraph(_clean(line), s['body']))
    return story


# ReportLab writes its name into a PDF comment in the header and trailer.
# Blank them in place (same length, so xref offsets stay valid).
_GENERATOR_COMMENTS = (b'ReportLab Generated PDF document http://www.reportlab.com',
                       b'ReportLab generated PDF document -- digest (http://www.reportlab.com)')


def _scrub_generator_tags(pdf: bytes) -> bytes:
    for marker in _GENERATOR_COMMENTS:
        pdf = pdf.replace(marker, b' ' * len(marker))
    return pdf


def _render(data: dict, layout: Layout, pagesize) -> tuple[bytes, int]:
    font = _DOCUMENT_FONT.get()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=pagesize, leftMargin=layout.margin, rightMargin=layout.margin,
        topMargin=layout.margin, bottomMargin=layout.margin,
        title=f"{data['name']} - Resume", author=data['name'], subject='Resume', creator='',
        producer='', keywords='', lang=_DOCUMENT_LANG.get(), displayDocTitle=1,
        # Otherwise ReportLab references a non-embedded Helvetica as the canvas default.
        initialFontName=font, initialFontSize=layout.body, initialLeading=layout.leading)
    doc.build(_story(data, layout, font))
    return _scrub_generator_tags(buffer.getvalue()), doc.page


# ── Strict one-page condensing ───────────────────────────────────────────────

def _bullet_priority(text: str, keywords) -> float:
    from backend.app.utils.resume_quality import contains
    score = sum(1 for k in keywords if contains(text, k))
    if re.search(r'\d', text):
        score += 0.5  # quantified achievements are kept preferentially
    return score


def _first_sentences(text: str, count: int) -> str:
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return ' '.join(sentences[:count]).strip()


def _condense_steps(data: dict, keywords):
    """Yield (description, data) with progressively less secondary content.

    Never removes an employer, job title, employment date, degree or
    certification. Order: tool lines, summary, secondary projects, trailing
    low-priority bullets from the oldest roles, additional information.
    """
    data = copy.deepcopy(data)
    for job in reversed(data['experience']):
        if job['environment']:
            job['environment'] = ''
            yield 'Removed tool lists already covered by Skills', data
    for count in (2, 1):
        shorter = _first_sentences(data['summary'], count)
        if data['summary'] and shorter != data['summary']:
            data['summary'] = shorter
            yield f'Shortened summary to {count} sentence{"s" if count > 1 else ""}', data
    for floor in (1, 0):
        for project in reversed(data['projects'][1:]):
            while len(project['bullets']) > floor:
                project['bullets'] = _drop_lowest(project['bullets'], keywords)
                yield f'Shortened project "{project["title"]}"', data
    if data['projects'] and len(data['projects'][0]['bullets']) > 1:
        data['projects'][0]['bullets'] = data['projects'][0]['bullets'][:1]
        yield 'Shortened main project', data
    for floor in (4, 3, 2, 1):
        # Oldest roles first; the most recent role keeps the most detail.
        for job in reversed(data['experience']):
            while len(job['bullets']) > floor:
                job['bullets'] = _drop_lowest(job['bullets'], keywords)
                yield f'Shortened {job["role"]} at {job["company"]}', data
    while len(data['projects']) > 1:
        removed = data['projects'].pop()
        yield f'Removed secondary project "{removed["title"]}"', data
    if data['additional_information']:
        data['additional_information'] = ''
        yield 'Removed additional information', data
    for job in reversed(data['experience'][1:]):
        if job['bullets']:
            job['bullets'] = []
            yield f'Kept only title, employer and dates for {job["role"]} at {job["company"]}', data
    if data['projects']:
        data['projects'] = []
        yield 'Removed projects', data


def _drop_lowest(bullets: list[str], keywords) -> list[str]:
    scores = [(_bullet_priority(b, keywords), -i) for i, b in enumerate(bullets)]
    drop = scores.index(min(scores))  # lowest priority; ties remove the later bullet
    return bullets[:drop] + bullets[drop + 1:]


def _page_count(pdf: bytes) -> int:
    from pypdf import PdfReader
    return len(PdfReader(BytesIO(pdf)).pages)


def strip_branding(data: dict) -> dict:
    """Branding/watermark removal on every rendered field."""
    from backend.app.utils.sanitize import clean_resume_strings
    return normalize_resume_data(clean_resume_strings(data))


def export_resume(resume_data, region: str | None = None, page_size: str | None = None,
                  priority_keywords=None, max_pages=None, **_ignored) -> ExportResult:
    """Render a one- or two-page resume and report what was done to fit it.

    ``max_pages`` is 1, 2 or 'auto' (default: 1 for US/CA, 'auto' elsewhere).
    'auto' uses one page when the resume fits one page at any layout profile
    without removing anything, otherwise up to two. Layout profiles are tried
    first (standard -> balanced -> compact); only if the content still
    overflows the limit is secondary content condensed, and every cut is
    listed in the warnings. The page count is verified with pypdf.
    """
    data = strip_branding(resume_data)
    if not has_exportable_content(data):
        raise ResumeExportError('Resume content could not be read, so no resume was generated. '
                                'Please retry or upload a text-based PDF or DOCX.')
    from backend.app.utils.language import detect_language, resume_text
    font = choose_font(data)
    lang = detect_language(resume_text(data))
    token, lang_token = _DOCUMENT_FONT.set(font), _DOCUMENT_LANG.set(lang)
    try:
        result = _export(data, region, page_size, priority_keywords, max_pages)
    finally:
        _DOCUMENT_FONT.reset(token)
        _DOCUMENT_LANG.reset(lang_token)
    result.font, result.lang = font, lang
    return result


def _export(data: dict, region, page_size, priority_keywords, max_pages=None) -> ExportResult:
    region = resolve_region(region)
    setting = resolve_max_pages(region, max_pages)
    limit = 1 if setting == 1 else 2
    found = personal_details(data)
    data = apply_region_rules(data, region)
    if page_size:
        size_name = page_size.strip().upper()
        if size_name not in ('A4', 'LETTER'):
            raise ResumeExportError('Page size must be A4 or LETTER.')
    else:
        size_name = 'LETTER' if region in LETTER_REGIONS else 'A4'
    pagesize = LETTER if size_name == 'LETTER' else A4
    keywords = [k for k in (priority_keywords or []) if isinstance(k, str) and k.strip()]

    warnings = []
    missing = _unsupported_characters(data)
    if missing:
        warnings.append('Some characters are not supported by the installed resume fonts and may not display: '
                        + ''.join(missing[:20]))
    if found:
        if region in STRIP_PERSONAL_REGIONS:
            warnings.append(f'Removed personal details employers in this region do not expect: {", ".join(found)}.')
        else:
            warnings.append(f'Kept personal details from your resume ({", ".join(found)}). Remove them if the '
                            'employer or country does not ask for them.')

    # One page first: for a 1-page setting, and for 'auto' when it fits without cuts.
    pdf, pages, layout = b'', 0, LAYOUTS[0]
    for target in ((1,) if limit == 1 else (1, 2)):
        for layout in LAYOUTS:
            pdf, pages = _render(data, layout, pagesize)
            if pages <= target:
                break
        if pages <= target:
            break
    condensed_items, content = [], data
    if pages > limit:
        for description, candidate in _condense_steps(data, keywords):
            if not condensed_items or condensed_items[-1] != description:
                condensed_items.append(description)
            pdf, pages = _render(candidate, layout, pagesize)
            content = copy.deepcopy(candidate)
            if pages <= limit:
                break
    pages = _page_count(pdf) if pdf else pages
    length = 'one page' if limit == 1 else 'two pages'
    if pages > limit:
        raise ResumeExportError(f'The resume could not be fitted on {length} without removing employers, titles, '
                                'dates, degrees or certifications. Please shorten the source resume.')
    if condensed_items:
        warnings.append(f'To fit {length}, some lower-priority content was shortened: '
                        + '; '.join(condensed_items[:6]) + ('...' if len(condensed_items) > 6 else '') + '.')
    _record_fit(layout.name, bool(condensed_items))
    return ExportResult(pdf=pdf, pages=pages, page_size=size_name, region=region, layout=layout.name,
                        condensed=bool(condensed_items), condensed_items=condensed_items, warnings=warnings,
                        max_pages=setting, content=content)


def _record_fit(layout: str, condensed: bool):
    try:
        from backend.app.core.metrics import PDF_SINGLE_PAGE_PASS
        PDF_SINGLE_PAGE_PASS.labels(layout=layout, condensed=str(condensed).lower()).inc()
    except Exception:
        pass


def generate_optimized_resume(filename=None, score=0, improvements=None, resume_data=None,
                              region=None, page_size=None, priority_keywords=None, **_ignored):
    """Backward-compatible wrapper returning a BytesIO.

    ``score`` and ``improvements`` are deliberately ignored: optimizer notes
    and scores must never be printed on a candidate's resume.
    """
    result = export_resume(resume_data, region=region, page_size=page_size, priority_keywords=priority_keywords)
    buffer = BytesIO(result.pdf)
    buffer.export_info = result.info()
    buffer.seek(0)
    return buffer


def download_filename(name) -> tuple[str, str]:
    """Return (ascii_fallback, utf8_name) e.g. "Olajide_Ebun_Adewale_Resume.pdf"."""
    text = _text(name)
    # Keep letters, digits and combining marks (e.g. Yoruba tone marks).
    utf8 = ''.join(c if c.isalnum() or c == '-' or unicodedata.combining(c) else '_' for c in text)
    utf8 = re.sub(r'_+', '_', utf8).strip('_')
    ascii_name = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode()
    ascii_name = re.sub(r'[^A-Za-z0-9\-]+', '_', ascii_name).strip('_')
    ascii_name = (ascii_name[:80] or 'Candidate') + '_Resume.pdf'
    utf8 = (utf8[:80] or 'Candidate') + '_Resume.pdf'
    return ascii_name, utf8
