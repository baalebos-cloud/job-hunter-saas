"""ATS-friendly, single-column resume export.

Rules enforced here (see docs in the PR "fix/resume-global-standard"):
* Only candidate content is rendered. Optimizer notes, scores, branding and
  "AI optimised" labels never enter the document; ``improvements`` and
  ``score`` are accepted for backwards compatibility and ignored.
* No tables, images or colour-coded meaning (one accent colour for the name
  and headings only). Text is selectable, uses an embedded TTF (Carlito, or
  DejaVu Sans when Carlito lacks a glyph) and real text bullets. Dates sit
  right-aligned on the entry's first line as a separate text run.
* Section order: Professional Summary, Core Skills, Professional Experience,
  Selected Projects, Certifications, Education, Additional Information
  (empty sections omitted).
* Page size follows the candidate's region: US Letter for US/CA, A4 otherwise.
* An adaptive fitting pass tightens layout (never below 10pt body text) to
  fit the page budget; content is only condensed when a strict one-page
  document is explicitly requested.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate

FONT_DIRECTORY = Path(__file__).resolve().parents[1] / 'assets' / 'fonts'
# Carlito is metric-compatible with Calibri. DejaVu Sans covers far more
# scripts and is used for the whole document when Carlito lacks a glyph, so a
# resume never mixes fonts or silently loses characters.
FONT_FAMILIES = {
    'Carlito': ('Carlito-Regular.ttf', 'Carlito-Bold.ttf', 'Carlito-Italic.ttf', 'Carlito-BoldItalic.ttf'),
    'DejaVuSans': ('DejaVuSans.ttf', 'DejaVuSans-Bold.ttf', 'DejaVuSans-Oblique.ttf', 'DejaVuSans-BoldOblique.ttf'),
}
PRIMARY_FONT, FALLBACK_FONT = 'Carlito', 'DejaVuSans'
for _family, (_regular, _bold, _italic, _bold_italic) in FONT_FAMILIES.items():
    for _suffix, _file in (('', _regular), ('-Bold', _bold), ('-Italic', _italic), ('-BoldItalic', _bold_italic)):
        pdfmetrics.registerFont(TTFont(_family + _suffix, str(FONT_DIRECTORY / _file)))
    pdfmetrics.registerFontFamily(_family, normal=_family, bold=f'{_family}-Bold',
                                  italic=f'{_family}-Italic', boldItalic=f'{_family}-BoldItalic')

ACCENT_COLOR = colors.HexColor('#1F4E79')   # name, headings and rules only; carries no meaning
TEXT_COLOR = colors.HexColor('#1A1A1A')
MUTED_COLOR = colors.HexColor('#555555')
MUTED_HEX = '#555555'

REGIONS = ('US', 'CA', 'UK', 'EU', 'NG', 'OTHER')
LETTER_REGIONS = {'US', 'CA'}
# Personal details that US/Canadian conventions (and anti-discrimination
# guidance) exclude. They are never added; for US/CA they are also dropped
# when the source resume contains them.
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


def apply_region_rules(data: dict, region: str) -> dict:
    """US/CA convention: no DOB, marital status, photo or similar details."""
    if resolve_region(region) not in LETTER_REGIONS:
        return data
    lines = [line for line in data.get('additional_information', '').splitlines() if not PERSONAL_DETAIL_PATTERN.search(line)]
    contact = ' | '.join(p for p in data.get('contact', '').split(' | ') if not PERSONAL_DETAIL_PATTERN.search(p))
    return {**data, 'additional_information': '\n'.join(lines), 'contact': contact}


def merge_confirmed_keywords(data: dict, keywords) -> dict:
    """Add skills the candidate explicitly confirmed. Nothing else is added."""
    data = normalize_resume_data(data)
    existing = {s.casefold() for values in data['skills'].values() for s in values}
    confirmed = [k for k in _unique(_lines(keywords)) if k.casefold() not in existing]
    if not confirmed:
        return data
    skills = dict(data['skills'])
    if list(skills) == ['Skills'] or not skills:
        skills['Skills'] = skills.get('Skills', []) + confirmed
    else:
        skills['Additional Skills'] = skills.get('Additional Skills', []) + confirmed
    return {**data, 'skills': skills}


# ── Rendering ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Layout:
    body: float
    leading: float
    margin: float
    name: float
    section_gap: float
    entry_gap: float


LAYOUTS = (
    Layout(body=10.5, leading=13.5, margin=54, name=17, section_gap=9, entry_gap=5),   # 0.75in margins
    Layout(body=10, leading=12.5, margin=43, name=16, section_gap=6, entry_gap=3),     # 0.6in margins
    Layout(body=10, leading=12, margin=36, name=15, section_gap=4, entry_gap=2),       # 0.5in margins
)
MIN_BODY_FONT = 10


@dataclass
class ExportResult:
    pdf: bytes
    pages: int
    page_size: str
    region: str
    layout_pass: int
    font: str = PRIMARY_FONT
    condensed: bool = False
    warnings: list[str] = field(default_factory=list)

    def info(self) -> dict:
        return {'pages': self.pages, 'page_size': self.page_size, 'region': self.region, 'font': self.font,
                'layout_pass': self.layout_pass, 'condensed': self.condensed, 'warnings': list(self.warnings)}


def _clean(value) -> str:
    """Escape candidate text for ReportLab's mini-markup parser."""
    return escape(_text(value))


def _all_text(data: dict) -> str:
    parts = [data['name'], data['title'], data['contact'], data['summary'], data['additional_information']]
    parts += [item for values in data['skills'].items() for item in (values[0], ' '.join(values[1]))]
    parts += [str(v) for e in data['experience'] for v in e.values()]
    parts += [str(v) for p in data['projects'] for v in p.values()]
    parts += [str(v) for e in data['education'] for v in e.values()]
    parts += data['certifications']
    return ' '.join(parts)


def _missing_glyphs(family: str, text: str) -> set[str]:
    cmap = pdfmetrics.getFont(family).face.charToGlyph
    return {c for c in text if not c.isspace() and ord(c) not in cmap}


def choose_font(data: dict) -> tuple[str, list[str]]:
    """Return (font family, characters neither bundled font can draw).

    Carlito is used when it covers every character, combining marks included;
    otherwise the whole document uses DejaVu Sans. Unsupported characters are
    reported, never silently stripped.
    """
    text = _all_text(data)
    if not _missing_glyphs(PRIMARY_FONT, text):
        return PRIMARY_FONT, []
    missing = sorted(c for c in _missing_glyphs(FALLBACK_FONT, text)
                     if ord(c) > 0x7f and not unicodedata.combining(c) and unicodedata.category(c)[0] in 'LNPS')
    return FALLBACK_FONT, missing


class SectionHeading(Flowable):
    """Bold accent-coloured caps over a thin rule, kept with the content that follows."""

    def __init__(self, text: str, font: str, size: float, space_before: float):
        super().__init__()
        self.text, self.font, self.size = text.upper(), font, size
        self.keepWithNext = 1
        self.spaceBefore, self.spaceAfter = space_before, 4

    def wrap(self, available_width, available_height):
        self.width = available_width
        return available_width, self.size + 5

    def draw(self):
        canvas = self.canv
        canvas.setFillColor(ACCENT_COLOR)
        canvas.setFont(self.font, self.size)
        canvas.drawString(0, 5, self.text)
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
    bold, italic = f'{font}-Bold', f'{font}-Italic'
    base = dict(fontName=font, fontSize=layout.body, leading=layout.leading, textColor=TEXT_COLOR, splitLongWords=1)
    return {
        'name': ParagraphStyle('Name', **{**base, 'fontName': bold, 'fontSize': layout.name, 'leading': layout.name * 1.25,
                                          'textColor': ACCENT_COLOR, 'alignment': TA_CENTER}),
        'title': ParagraphStyle('Title', **{**base, 'textColor': MUTED_COLOR, 'alignment': TA_CENTER, 'spaceBefore': 1}),
        'contact': ParagraphStyle('Contact', **{**base, 'textColor': MUTED_COLOR, 'alignment': TA_CENTER, 'spaceBefore': 1}),
        'body': ParagraphStyle('Body', **base),
        'skill': ParagraphStyle('Skill', **{**base, 'spaceAfter': 1.5}),
        'entry': ParagraphStyle('Entry', **{**base, 'fontName': bold, 'spaceBefore': layout.entry_gap + 3}),
        'meta': ParagraphStyle('Meta', **{**base, 'fontName': italic, 'textColor': MUTED_COLOR, 'spaceAfter': 1.5}),
        'bullet': ParagraphStyle('Bullet', **{**base, 'leftIndent': 16, 'bulletIndent': 5, 'spaceAfter': 1.5,
                                              'bulletFontName': font, 'bulletFontSize': layout.body}),
    }


def _bullet_markup(text: str) -> str:
    """Bold a short lead-in written as "Label: sentence" (at most six words, no full stop)."""
    head, sep, tail = text.partition(': ')
    if sep and tail and 2 <= len(head) <= 48 and len(head.split()) <= 6 and '.' not in head:
        return f'<b>{_clean(head)}:</b> {_clean(tail)}'
    return _clean(text)


def _muted(text: str, font: str) -> str:
    return f"<font name='{font}' color='{MUTED_HEX}'>{_clean(text)}</font>"


def _tech_line(value: str) -> str:
    return ' · '.join(_split_skills(value))


def _story(data: dict, layout: Layout, font: str) -> list:
    s = _styles(layout, font)
    story = []

    def heading(title):
        story.append(SectionHeading(title, f'{font}-Bold', max(MIN_BODY_FONT, layout.body), layout.section_gap + 4))

    def entry(primary, secondary, right, keep_with_next):
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


def _render(data: dict, layout: Layout, pagesize, font: str) -> tuple[bytes, int]:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=pagesize, leftMargin=layout.margin, rightMargin=layout.margin,
        topMargin=layout.margin * 0.8, bottomMargin=layout.margin * 0.8,
        title=f"{data['name']} - Resume", author=data['name'], subject='Resume', creator='',
        producer='', keywords='', lang='en', displayDocTitle=1,
        # Otherwise ReportLab references a non-embedded Helvetica as the canvas default.
        initialFontName=font, initialFontSize=layout.body, initialLeading=layout.leading)
    doc.build(_story(data, layout, font))
    return buffer.getvalue(), doc.page


def _condense(data: dict, keep: int, priority_keywords) -> dict:
    """Trim bullets to ``keep`` per role/project, preferring ones that mention
    priority keywords. Never removes an employer, degree or certification."""
    keys = [k.casefold() for k in priority_keywords or [] if k]

    def pick(items):
        if len(items) <= keep:
            return items
        ranked = sorted(range(len(items)), key=lambda i: (-sum(k in items[i].casefold() for k in keys), i))
        chosen = sorted(ranked[:keep])
        return [items[i] for i in chosen]
    return {**data,
            'experience': [{**e, 'bullets': pick(e['bullets'])} for e in data['experience']],
            'projects': [{**p, 'bullets': pick(p['bullets'])} for p in data['projects']]}


def export_resume(resume_data, region: str | None = None, page_size: str | None = None,
                  max_pages: int = 2, priority_keywords=None) -> ExportResult:
    """Render the resume and report page metrics.

    ``max_pages=1`` enables strict one-page mode: after layout tightening, the
    lowest-relevance bullets are condensed. ``max_pages=2`` (default) only
    tightens layout and warns if the document still exceeds two pages.
    """
    data = normalize_resume_data(resume_data)
    if not has_exportable_content(data):
        raise ResumeExportError('Resume content could not be read, so no resume was generated. '
                                'Please retry or upload a text-based PDF or DOCX.')
    region = resolve_region(region)
    data = apply_region_rules(data, region)
    if page_size:
        size_name = page_size.strip().upper()
        if size_name not in ('A4', 'LETTER'):
            raise ResumeExportError('Page size must be A4 or LETTER.')
    else:
        size_name = 'LETTER' if region in LETTER_REGIONS else 'A4'
    pagesize = LETTER if size_name == 'LETTER' else A4
    target = 1 if max_pages == 1 else 2

    warnings = []
    font, missing = choose_font(data)
    if missing:
        warnings.append('Some characters are not supported by the resume font and may not display: ' + ''.join(missing[:20]))

    pdf, pages, used, condensed = b'', 0, 0, False
    # Try to fit on one page with layout changes only; never drop content here.
    for index, layout in enumerate(LAYOUTS, start=1):
        pdf, pages = _render(data, layout, pagesize, font)
        used = index
        if pages <= 1:
            break
    if pages > 1 and target == 2:
        # Two pages are acceptable: use the most readable layout that fits two.
        for index, layout in enumerate(LAYOUTS, start=1):
            pdf, pages = _render(data, layout, pagesize, font)
            used = index
            if pages <= 2:
                break
    if pages > 1 and target == 1:
        for keep in (4, 3, 2, 1):
            pdf, pages = _render(_condense(data, keep, priority_keywords), LAYOUTS[-1], pagesize, font)
            condensed = True
            if pages <= 1:
                break
    if pages > target:
        warnings.append(f'The resume is {pages} pages; most recruiters expect {"one page" if target == 1 else "one to two pages"}.')
    return ExportResult(pdf=pdf, pages=pages, page_size=size_name, region=region, font=font,
                        layout_pass=used, condensed=condensed, warnings=warnings)


def generate_optimized_resume(filename=None, score=0, improvements=None, resume_data=None,
                              region=None, page_size=None, max_pages=2, priority_keywords=None):
    """Backward-compatible wrapper returning a BytesIO.

    ``score`` and ``improvements`` are deliberately ignored: optimizer notes
    and scores must never be printed on a candidate's resume.
    """
    result = export_resume(resume_data, region=region, page_size=page_size,
                           max_pages=max_pages, priority_keywords=priority_keywords)
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
