"""Reading order for resume files.

PDF: two-column layouts (Canva, Zety, Europass sidebars) are read column by
column. A page is treated as two columns only when an empty vertical band runs
through most of its lines and both sides carry real text; otherwise it is read
exactly as before (``extract_text(x_tolerance=1)``), so ordinary one-column
resumes, including the ones Baalebos exports, are unchanged.

DOCX: the body plus every section's headers and footers (default, first-page
and even-page), where many templates put the name, email and phone.
"""
from __future__ import annotations

from dataclasses import dataclass

X_TOLERANCE = 1
BAND = 6.0                 # half-width of the empty band a gutter needs (pt): a 12pt-wide gap
LINE_TOLERANCE = 3.0       # words whose tops differ by less than this share a line
MIN_SPLIT_LINES = 0.5      # share of lines that must leave the band empty
MIN_SIDE_WORDS = 0.15      # share of words each column must hold
MIN_BLOCK_LINES = 3        # shorter runs of split lines are read full-width


@dataclass
class _Line:
    top: float
    bottom: float
    words: list


def _lines(words) -> list[_Line]:
    lines: list[_Line] = []
    for word in sorted(words, key=lambda w: (w['top'], w['x0'])):
        if lines and abs(word['top'] - lines[-1].top) <= LINE_TOLERANCE:
            lines[-1].words.append(word)
            lines[-1].bottom = max(lines[-1].bottom, word['bottom'])
        else:
            lines.append(_Line(word['top'], word['bottom'], [word]))
    return lines


def _covers(line: _Line, x: float) -> bool:
    return any(w['x0'] - BAND < x < w['x1'] + BAND for w in line.words)


def find_gutter(words, width: float) -> float | None:
    """x of a column gutter, or None for a one-column page."""
    lines = _lines(words)
    if len(lines) < 6:
        return None
    best, best_free = None, 0
    x = width * 0.2
    while x <= width * 0.8:
        free = sum(1 for line in lines if not _covers(line, x))
        if free > best_free:
            best, best_free = x, free
        x += 2.0
    if best is None or best_free < MIN_SPLIT_LINES * len(lines):
        return None
    split = [line for line in lines if not _covers(line, best)]
    left = sum(1 for line in split for w in line.words if w['x1'] <= best)
    right = sum(1 for line in split for w in line.words if w['x0'] >= best)
    total = left + right
    if not total or left < MIN_SIDE_WORDS * total or right < MIN_SIDE_WORDS * total:
        return None
    # Text must sit on both sides across several lines, not one stray date column.
    if sum(1 for line in split if any(w['x0'] >= best for w in line.words)) < MIN_BLOCK_LINES:
        return None
    if sum(1 for line in split if any(w['x1'] <= best for w in line.words)) < MIN_BLOCK_LINES:
        return None
    return best


def _segments(lines: list[_Line], gutter: float):
    """Consecutive runs of ('full' | 'split', top, bottom)."""
    runs: list[list] = []          # [kind, [lines]]
    for line in lines:
        kind = 'full' if _covers(line, gutter) else 'split'
        if runs and runs[-1][0] == kind:
            runs[-1][1].append(line)
        else:
            runs.append([kind, [line]])
    out: list[list] = []

    def emit(kind, chunk):
        if not chunk:
            return
        if out and out[-1][0] == kind:
            out[-1][2] = chunk[-1].bottom
        else:
            out.append([kind, chunk[0].top, chunk[-1].bottom])

    for kind, chunk in runs:
        if kind == 'split':
            # Lines above the point where both columns have started (a name or
            # title sitting on one side) read first, full width.
            has_left = [any(w['x1'] <= gutter for w in line.words) for line in chunk]
            has_right = [any(w['x0'] >= gutter for w in line.words) for line in chunk]
            start = max(has_left.index(True) if True in has_left else len(chunk),
                        has_right.index(True) if True in has_right else len(chunk))
            emit('full', chunk[:start])
            chunk = chunk[start:]
            # A short split run (a header line with a right-aligned date) reads full width.
            if len(chunk) < MIN_BLOCK_LINES:
                kind = 'full'
        emit(kind, chunk)
    return out


def pdf_page_text(page) -> str:
    """Text of one pdfplumber page in reading order."""
    words = page.extract_words(x_tolerance=X_TOLERANCE)
    gutter = find_gutter(words, float(page.width)) if words else None
    if gutter is None:
        return page.extract_text(x_tolerance=X_TOLERANCE) or ''
    width, height = float(page.width), float(page.height)
    parts = []
    for kind, top, bottom in _segments(_lines(words), gutter):
        y0, y1 = max(0.0, top - 1), min(height, bottom + 1)
        boxes = [(0, y0, width, y1)] if kind == 'full' else [(0, y0, gutter, y1), (gutter, y0, width, y1)]
        for box in boxes:
            text = page.within_bbox(box).extract_text(x_tolerance=X_TOLERANCE) or ''
            if text.strip():
                parts.append(text.strip())
    return '\n'.join(parts)


def docx_text(doc) -> str:
    """Headers, body and footers of a python-docx Document, without repeats."""
    from docx.oxml.ns import qn

    def blocks(element) -> list[str]:
        # Paragraphs and tables in document order (tables keep their cell order).
        return [' '.join(t.text or '' for t in child.iter(qn('w:t'))) for child in element]

    def part_lines(part) -> list[str]:
        if part is None or getattr(part, 'is_linked_to_previous', False):
            return []
        try:
            return blocks(part._element)
        except Exception:
            return []

    head, foot, seen = [], [], set()

    def add(target, lines):
        for line in lines:
            key = ' '.join(line.split()).casefold()
            if key and key not in seen:
                seen.add(key)
                target.append(line)

    for section in doc.sections:
        for name in ('first_page_header', 'header', 'even_page_header'):
            add(head, part_lines(getattr(section, name, None)))
        for name in ('first_page_footer', 'footer', 'even_page_footer'):
            add(foot, part_lines(getattr(section, name, None)))
    body = blocks(doc.element.body)
    return '\n'.join([*head, *body, *foot]).strip()
