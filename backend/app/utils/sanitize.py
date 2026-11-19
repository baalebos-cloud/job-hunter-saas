"""Sanitisation for untrusted resume / job-description text.

Two independent concerns:

* ``sanitize_untrusted_text`` removes markup and PDF-injection tokens so that
  neither the LLM prompt nor ReportLab's mini-markup parser ever receives
  active content (``<script>``, ``<para>``, ``/JavaScript`` ...).
* ``strip_watermarks_and_branding`` removes resume-builder / AI-tool
  branding, page counters and optimiser commentary while keeping the real
  candidate content that shares the same line.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# ── Untrusted text ───────────────────────────────────────────────────────────

_CONTROL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]')
# Executable / layout containers: drop the element *and* its contents.
_ACTIVE_BLOCKS = re.compile(r'<\s*(script|style|iframe|object|embed|svg|math|template)\b[^>]*>.*?<\s*/\s*\1\s*>',
                            re.IGNORECASE | re.DOTALL)
_ACTIVE_OPEN = re.compile(r'<\s*(script|style|iframe|object|embed|svg|math|template)\b[^>]*>', re.IGNORECASE)
# Any other HTML/XML/ReportLab tag (<para>, <font>, <a href>, <img/>, </b> ...).
# Requires a letter (or / or !) after "<" so text such as "<5s" or "a < b" survives.
_TAG = re.compile(r'<\s*(?:/\s*)?(?:[A-Za-z][\w:.-]*|!--.*?--|!\[CDATA\[.*?\]\])(?:\s[^<>]*)?/?\s*>', re.DOTALL)
_ENTITY_SCRIPT = re.compile(r'(?:javascript|vbscript|data)\s*:', re.IGNORECASE)
# PDF dictionary keys / operators that trigger actions or embedded content.
_PDF_TOKENS = re.compile(r'/(?:JavaScript|JS|OpenAction|AA|Launch|EmbeddedFile|EmbeddedFiles|RichMedia|XFA|AcroForm|SubmitForm|ImportData|GoToR|GoToE)\b'
                         r'|\b\d+\s+\d+\s+obj\b|\bendobj\b|\bendstream\b|\bstartxref\b|%%EOF', re.IGNORECASE)


@dataclass
class SanitizeReport:
    text: str
    blocked: int


def sanitize_untrusted_text(value, *, report: bool = False):
    """Return NFKC-normalised text without markup, control characters or
    PDF action tokens. Visible prose (including "R&D" and "<5s") is kept."""
    text = unicodedata.normalize('NFKC', str(value or ''))
    blocked = 0
    for pattern in (_ACTIVE_BLOCKS, _ACTIVE_OPEN, _TAG, _ENTITY_SCRIPT, _PDF_TOKENS):
        text, count = pattern.subn(' ', text)
        blocked += count
    text, count = _CONTROL.subn('', text)
    # Control characters are noise, not attacks; do not count them as blocks.
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r' *\n *', '\n', text).strip()
    if blocked:
        _record_block(blocked)
    return SanitizeReport(text, blocked) if report else text


def _record_block(count: int):
    try:
        from backend.app.core.metrics import SANITIZATION_BLOCKS
        SANITIZATION_BLOCKS.inc(count)
    except Exception:  # metrics are optional in scripts and tests
        pass


# ── Watermarks / branding ────────────────────────────────────────────────────

# Resume builders, AI writers and this product. Bare names that are also real
# skills (e.g. "Canva") are only removed inside a branding phrase.
BRANDS = [
    r'baalebos(?:\s+cloud)?(?:\s+ai)?', r'baalebo\.xyz', r'canva', r'resume\.io', r'zety(?:\.com)?',
    r'novoresume(?:\.com)?', r'kickresume(?:\.com)?', r'enhancv(?:\.com)?', r'resume\s*genius', r'resumegenius\.com',
    r'my\s*perfect\s*resume', r'livecareer(?:\.com)?', r'resume\.com', r'resumelab(?:\.com)?', r'jobscan(?:\.co)?',
    r'teal(?:hq)?(?:\.com)?', r'rezi(?:\.ai)?', r'resume\s*worded', r'visualcv(?:\.com)?', r'flowcv(?:\.com)?',
    r'chat\s*gpt', r'openai', r'claude(?:\.ai)?', r'gemini', r'copilot', r'grammarly', r'microsoft\s+word\s+templates?',
    r'google\s+docs?\s+templates?', r'indeed\s+resume\s+builder', r'linkedin\s+resume\s+builder',
]
_BRAND = r'(?:' + '|'.join(BRANDS) + r')'
# Domains of resume builders and this product, removed wherever they stand alone.
_BUILDER_ONLY = re.compile(
    r'^\s*(?:www\.)?(?:baalebos(?:\s+cloud)?(?:\s+ai)?|baalebo\.xyz|resume\.io|zety\.com|novoresume\.com|kickresume\.com|'
    r'enhancv\.com|resumegenius\.com|myperfectresume\.com|livecareer\.com|resumelab\.com|flowcv\.com|visualcv\.com)\s*$',
    re.IGNORECASE)
_BRANDING_PHRASE = re.compile(
    r'(?:\b(?:powered|generated|created|made|designed|built|optimi[sz]ed|formatted|written|crafted|enhanced|'
    r'tailored|produced|exported|rewritten|polished|template)\s+(?:by|with|using|on|via|in|from|through)\s+'
    r'(?:the\s+)?' + _BRAND + r'(?:\s+(?:cloud|ai|app|pro|builder|resume\s+builder|template|\.com))*\b\.?'
    r'|\b(?:resume|cv)\s+(?:template\s+)?(?:by|from|via)\s+' + _BRAND + r'\b\.?'
    r'|\bai[-\s]optimi[sz]ed(?:\s+(?:resume|cv|by\s+' + _BRAND + r'))?\b'
    r'|\b(?:optimi[sz]ed|scored|checked)\s+for\s+ats\s+by\s+' + _BRAND + r'\b'
    r'|\bats\s+score\s*:?\s*\d+(?:\.\d+)?\s*%?)',
    re.IGNORECASE)
_PAGE_COUNTER = re.compile(r'^\s*(?:-\s*)?page\s+\d+(?:\s*(?:of|/)\s*\d+)?(?:\s*-)?\s*$|^\s*\d+\s*/\s*\d+\s*$', re.IGNORECASE)
_PAGE_COUNTER_INLINE = re.compile(r'\bpage\s+\d+\s*(?:of|/)\s*\d+\b', re.IGNORECASE)
# Optimiser / tool commentary: the rest of the segment is not candidate content.
_COMMENTARY = re.compile(
    r'^\s*(?:ats\s+(?:improvement\s+)?notes?|improvement\s+notes?|optimi[sz]ation\s+notes?|ai\s+notes?|'
    r'notes?\s+to\s+(?:recruiter|self|candidate)|suggestions?|tips?|recommendations?|added\s+to\s+resume)\s*:.*$'
    r'|^\s*add\s+.+\s+to\s+your\s+(?:skills?|experience|summary)(?:\s+section)?\.?\s*$'
    r'|^\s*(?:incorporate|include)\s+.+\s+(?:naturally\s+)?into\s+your\s+(?:resume|experience|bullets?).*$',
    re.IGNORECASE)
# Unambiguous optimiser-note markers also end a segment mid-line.
_COMMENTARY_INLINE = re.compile(
    r'\b(?:ats\s+(?:improvement\s+)?notes?|improvement\s+notes?|optimi[sz]ation\s+notes?|ai\s+notes?)\s*:.*$',
    re.IGNORECASE)
_SEPARATORS = re.compile(r'(\s*[|\u2022\u00b7\u25cf\u2016]\s*)')


def strip_watermarks_and_branding(value) -> str:
    """Remove branding, watermarks, page counters and optimiser commentary.

    Lines are split into segments on "|", "•" and "·" so that real
    content sharing a line survives:
    "Senior Software Engineer | Powered by Baalebos Cloud" -> "Senior Software Engineer".
    """
    out_lines = []
    for line in str(value or '').splitlines():
        parts = _SEPARATORS.split(line)
        segments, separators = parts[0::2], parts[1::2]
        kept = []
        for index, segment in enumerate(segments):
            cleaned = _clean_segment(segment)
            if cleaned:
                kept.append((separators[index - 1] if index and kept else '', cleaned))
        text = ''.join(sep + seg for sep, seg in kept).strip()
        if text:
            out_lines.append(text)
        elif not line.strip():
            out_lines.append('')
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(out_lines)).strip()


def _clean_segment(segment: str) -> str:
    if _COMMENTARY.match(segment) or _PAGE_COUNTER.match(segment) or _BUILDER_ONLY.match(segment):
        return ''
    segment = _COMMENTARY_INLINE.sub('', segment)
    segment = _BRANDING_PHRASE.sub('', segment)
    segment = _PAGE_COUNTER_INLINE.sub('', segment)
    segment = re.sub(r'\(\s*\)|\[\s*\]', '', segment)
    segment = re.sub(r'\s{2,}', ' ', segment)
    segment = re.sub(r'^[\s,;:\-\u2013\u2014]+|[\s,;:\-\u2013\u2014]+$', '', segment)
    if _BUILDER_ONLY.match(segment):
        return ''
    return segment


def clean_resume_strings(data):
    """Apply sanitisation + branding removal to every string in a structure."""
    if isinstance(data, str):
        return strip_watermarks_and_branding(sanitize_untrusted_text(data))
    if isinstance(data, list):
        return [item for item in (clean_resume_strings(v) for v in data) if item not in ('', None, [], {})]
    if isinstance(data, dict):
        return {k: clean_resume_strings(v) for k, v in data.items()}
    return data
