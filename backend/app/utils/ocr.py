"""Bounded OCR fallback for scanned or font-damaged PDFs.

Triggered when text extraction yields too little text or ``(cid:N)`` glyph
codes. Uses Tesseract via pdf2image (poppler) inside the API/worker image;
every call is bounded by a page cap, a DPI/pixel cap and a wall-clock
deadline, and a circuit breaker stops hammering a failing OCR engine.
"""
from __future__ import annotations

import io
import logging
import math
import os
import re
import threading
import time

logger = logging.getLogger(__name__)

OCR_MAX_PAGES = int(os.getenv('OCR_MAX_PAGES', '15'))
OCR_DPI = int(os.getenv('OCR_DPI', '200'))
OCR_MAX_DPI = 300
OCR_MAX_PIXELS_PER_PAGE = 25_000_000  # ~A4 at 600 dpi; protects memory
OCR_TIMEOUT_SECONDS = float(os.getenv('OCR_TIMEOUT_SECONDS', '12'))
CID_PATTERN = re.compile(r'\(cid:\d+\)')
# Latin-script languages are read together in one pass; other scripts are tried
# only when that pass finds too little text. Languages not installed are skipped.
OCR_LANGUAGES = os.getenv('OCR_LANGUAGES', 'eng+fra+deu+spa+por+ita')
OCR_FALLBACK_LANGUAGES = os.getenv('OCR_FALLBACK_LANGUAGES', 'ara,hin')
MIN_TEXT_CHARS = 40


class OcrUnavailable(RuntimeError):
    """OCR could not run (not installed, breaker open, timeout or failure)."""


class CircuitBreaker:
    """Opens after ``threshold`` consecutive failures for ``cooldown`` seconds."""

    def __init__(self, threshold: int = 3, cooldown: float = 60.0):
        self.threshold, self.cooldown = threshold, cooldown
        self._failures, self._opened_at = 0, None
        self._lock = threading.Lock()

    @property
    def is_open(self) -> bool:
        with self._lock:
            if self._opened_at is None:
                return False
            if time.monotonic() - self._opened_at >= self.cooldown:
                self._opened_at = None  # half-open: allow one trial
                self._failures = self.threshold - 1
                return False
            return True

    def success(self):
        with self._lock:
            self._failures, self._opened_at = 0, None

    def failure(self):
        with self._lock:
            self._failures += 1
            if self._failures >= self.threshold:
                self._opened_at = time.monotonic()


breaker = CircuitBreaker()


def needs_ocr(text: str) -> bool:
    stripped = (text or '').strip()
    return len(stripped) < MIN_TEXT_CHARS or bool(CID_PATTERN.search(stripped))


def _safe_dpi(width_pt: float, height_pt: float, dpi: int) -> int:
    dpi = max(72, min(dpi, OCR_MAX_DPI))
    area_in = max(width_pt / 72, 0.1) * max(height_pt / 72, 0.1)
    limit = int(math.sqrt(OCR_MAX_PIXELS_PER_PAGE / area_in))
    return max(50, min(dpi, limit))


_installed: set[str] | None = None


def _installed_languages(pytesseract) -> set[str]:
    global _installed
    if _installed is None:
        try:
            _installed = set(pytesseract.get_languages(config=''))
        except Exception:
            _installed = {'eng'}
    return _installed


def language_passes(installed: set[str]) -> list[str]:
    """Tesseract ``lang`` values to try in order, using only installed packs."""
    primary = [code for code in OCR_LANGUAGES.split('+') if code in installed] or ['eng']
    passes = ['+'.join(primary)]
    for code in (c.strip() for c in OCR_FALLBACK_LANGUAGES.split(',')):
        if code and code in installed:
            passes.append(f'{code}+eng' if 'eng' in installed else code)
    return passes


def _record(outcome: str):
    try:
        from backend.app.core.metrics import OCR_FALLBACKS
        OCR_FALLBACKS.labels(outcome=outcome).inc()
    except Exception:
        pass


def _read_image(pytesseract, image, deadline: float) -> str:
    """Latin languages first; other scripts only if that finds too little."""
    best = ''
    for lang in language_passes(_installed_languages(pytesseract)):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            if best:
                break
            raise TimeoutError('OCR deadline exceeded')
        text = pytesseract.image_to_string(image, lang=lang, timeout=max(1, remaining))
        if len(_letters(text)) > len(_letters(best)):
            best = text
        if len(_letters(best)) >= MIN_TEXT_CHARS:
            break
    return best


def _letters(text: str) -> str:
    return ''.join(ch for ch in (text or '') if ch.isalpha())


def ocr_pdf(content: bytes, *, max_pages: int = OCR_MAX_PAGES, dpi: int = OCR_DPI,
            timeout: float = OCR_TIMEOUT_SECONDS) -> str:
    """OCR a PDF page by page within a shared deadline."""
    if breaker.is_open:
        _record('breaker_open')
        raise OcrUnavailable('OCR is temporarily unavailable.')
    try:
        import pytesseract
        from pdf2image import convert_from_bytes
        from pypdf import PdfReader
    except ImportError as exc:
        _record('unavailable')
        raise OcrUnavailable('OCR is not installed.') from exc

    try:
        reader = PdfReader(io.BytesIO(content))
        page_count = len(reader.pages)
    except Exception as exc:
        _record('rejected')
        raise OcrUnavailable('OCR could not open this document.') from exc
    if page_count > max_pages:  # input limit, not an engine failure
        _record('rejected')
        raise OcrUnavailable(f'OCR is limited to {max_pages} pages.')
    deadline = time.monotonic() + timeout
    try:
        texts = []
        for number, page in enumerate(reader.pages, start=1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('OCR deadline exceeded')
            box = page.mediabox
            page_dpi = _safe_dpi(float(box.width), float(box.height), dpi)
            images = convert_from_bytes(content, dpi=page_dpi, first_page=number, last_page=number,
                                        timeout=max(1, int(remaining)), grayscale=True)
            for image in images:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('OCR deadline exceeded')
                texts.append(_read_image(pytesseract, image, deadline))
    except Exception as exc:  # timeout, poppler/tesseract failure, bad PDF
        breaker.failure()
        _record('failed')
        logger.warning('ocr_failed error_type=%s', type(exc).__name__)
        raise OcrUnavailable('OCR could not read this document in time.') from exc
    breaker.success()
    _record('success')
    return '\n'.join(t.strip() for t in texts if t and t.strip()).strip()
