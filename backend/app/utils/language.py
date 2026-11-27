"""Primary language and writing direction of a resume, for PDF metadata and layout.

Script first (Arabic, Hebrew, Devanagari, CJK, Cyrillic, Greek), then common
function words for Latin-script languages. Deliberately small and
deterministic; defaults to English when unsure.
"""
from __future__ import annotations

import re

_SCRIPTS = (
    ('ar', re.compile(r'[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]')),
    ('he', re.compile(r'[֐-׿יִ-ﭏ]')),
    ('hi', re.compile(r'[ऀ-ॿ]')),
    ('ja', re.compile(r'[぀-ヿ]')),
    ('ko', re.compile(r'[가-힯]')),
    ('zh', re.compile(r'[一-鿿]')),
    ('ru', re.compile(r'[Ѐ-ӿ]')),
    ('el', re.compile(r'[Ͱ-Ͽ]')),
)
RTL_LANGS = {'ar', 'he'}

_WORDS = {
    'en': 'the and of to in for with on at from as by is was are have has years experience',
    'fr': 'le la les des et du de un une pour avec dans sur par est expérience années compétences',
    'de': 'der die das und mit für von ist ein eine im zu auf bei erfahrung jahre kenntnisse',
    'es': 'el la los las y de del en con para por es un una experiencia años habilidades',
    'pt': 'o a os as e de do da em com para por é um uma experiência anos competências',
    'it': 'il lo la gli le e di del della in con per è un una esperienza anni competenze',
}
_WORD_SETS = {lang: set(words.split()) for lang, words in _WORDS.items()}
_TOKEN = re.compile(r"[^\W\d_]+", re.UNICODE)


def detect_language(text: str) -> str:
    """ISO 639-1 code of the main language; 'en' when unclear."""
    text = text or ''
    letters = sum(1 for ch in text if ch.isalpha())
    if not letters:
        return 'en'
    for code, pattern in _SCRIPTS:
        if len(pattern.findall(text)) >= 0.3 * letters:
            return code
    tokens = [t.casefold() for t in _TOKEN.findall(text)]
    scores = {lang: sum(1 for t in tokens if t in words) for lang, words in _WORD_SETS.items()}
    best = max(scores, key=lambda lang: (scores[lang], lang == 'en'))
    # Another language must clearly beat English, which resumes mix in freely.
    if best != 'en' and scores[best] < max(3, 1.5 * scores['en']):
        return 'en'
    return best


def is_rtl(text: str) -> bool:
    return detect_language(text) in RTL_LANGS


def resume_text(data: dict) -> str:
    """The visible prose of a normalized resume (for language detection)."""
    parts = [data.get('summary', ''), data.get('title', '')]
    for job in data.get('experience', []):
        parts += [job.get('role', ''), *job.get('bullets', [])]
    for project in data.get('projects', []):
        parts += [project.get('title', ''), *project.get('bullets', [])]
    return '\n'.join(str(p) for p in parts if p)
