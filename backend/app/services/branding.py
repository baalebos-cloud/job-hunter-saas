"""Apply an Enterprise account's branding to a resume export.

PDF: the stored, already-fitted one-page resume is left untouched; a header
(accent bar, logo, brand name) and a footer ("Prepared by <brand>") are drawn
inside the page margins, which are never smaller than 24 pt, so the branding
can never cover resume content. Word: the same header and footer are added
to the document's header and footer sections.
"""
from __future__ import annotations

import io
import re

from sqlalchemy.orm import Session

from backend.app.models.branding import DEFAULT_ACCENT, Branding

HEX = re.compile(r'^#[0-9a-fA-F]{6}$')
MAX_LOGO_BYTES = 1024 * 1024
LOGO_BOX = (600, 180)                 # stored logo is fitted into this box (pixels)
SAFE_MARGIN = 24                      # smallest margin any resume layout uses (pt)


def branding_owner_id(db: Session, user) -> int:
    """Members of an Enterprise team use the team owner's branding."""
    from backend.app.dependencies.plan_guard import team_owner
    owner = team_owner(db, user)
    return owner.id if owner is not None else user.id


def branding_for(db: Session, user) -> Branding | None:
    """The branding this user's downloads may use, or None (not Enterprise, or nothing set up)."""
    from backend.app.dependencies.plan_guard import plan_for
    if plan_for(db, user) != 'enterprise':
        return None
    row = db.get(Branding, branding_owner_id(db, user))
    return row if row is not None and row.configured else None


def clean_name(value: str | None) -> str | None:
    from backend.app.utils.pdf_generator import WIDE_LATIN_FONT, _coverage
    name = re.sub(r'\s+', ' ', (value or '')).strip()
    if not name:
        return None
    if len(name) > 60:
        raise ValueError('Use a brand name of up to 60 characters.')
    supported = _coverage(WIDE_LATIN_FONT)
    if any(ord(c) >= 0x80 and ord(c) not in supported for c in name) or any(ord(c) < 32 for c in name):
        raise ValueError('The brand name has characters that cannot be printed on the resume. '
                         'Use letters, numbers and common punctuation.')
    return name


def clean_color(value: str | None) -> str:
    value = (value or DEFAULT_ACCENT).strip()
    if not HEX.match(value):
        raise ValueError('Choose the accent colour as a hex value such as #059669.')
    return value.lower()


def clean_logo(raw: bytes) -> bytes:
    """Re-encode as PNG (proves it is an image, strips metadata) and fit it into LOGO_BOX."""
    from PIL import Image, ImageOps, UnidentifiedImageError
    if len(raw) > MAX_LOGO_BYTES:
        raise ValueError('The logo is too large. Use an image up to 1 MB.')
    try:
        image = Image.open(io.BytesIO(raw))
        if image.format not in ('PNG', 'JPEG', 'WEBP'):
            raise ValueError('Upload the logo as a PNG, JPG or WebP image.')
        image = ImageOps.exif_transpose(image).convert('RGBA')
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError('The logo could not be read. Upload a PNG, JPG or WebP image.') from exc
    image.thumbnail(LOGO_BOX)
    out = io.BytesIO()
    image.save(out, format='PNG', optimize=True)
    return out.getvalue()


def _font_for(text: str) -> str:
    from backend.app.utils.pdf_generator import PRIMARY_FONT, WIDE_LATIN_FONT, _coverage
    covered = _coverage(PRIMARY_FONT)
    return PRIMARY_FONT if all(ord(c) < 0x80 or ord(c) in covered for c in text) else WIDE_LATIN_FONT


def _rgb(hex_color: str):
    from reportlab.lib import colors
    return colors.HexColor(hex_color)


def brand_pdf(pdf: bytes, branding: Branding) -> bytes:
    """Return a copy of the PDF with the branding header and footer drawn in the margins."""
    from pypdf import PdfReader, PdfWriter
    from reportlab.lib import colors
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.pdfgen import canvas

    reader = PdfReader(io.BytesIO(pdf))
    writer = PdfWriter(clone_from=reader)
    accent = _rgb(branding.accent_color or DEFAULT_ACCENT)
    name = branding.brand_name
    for page in writer.pages:
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        layer = io.BytesIO()
        c = canvas.Canvas(layer, pagesize=(width, height))
        # Header: a thin accent bar on the top edge, then the logo or name at top right.
        c.setFillColor(accent)
        c.rect(0, height - 3, width, 3, stroke=0, fill=1)
        right = width - SAFE_MARGIN
        if branding.logo:
            logo = ImageReader(io.BytesIO(branding.logo))
            lw, lh = logo.getSize()
            box_h, box_w = 15.0, 100.0                                 # top 6 pt to 21 pt: inside the 24 pt margin
            scale = min(box_h / lh, box_w / lw)
            w, h = lw * scale, lh * scale
            c.drawImage(logo, right - w, height - 6 - h, width=w, height=h, mask='auto')
        elif name:
            font = _font_for(name)
            c.setFont(font, 8)
            c.setFillColor(accent)
            c.drawRightString(right, height - 15, name)
        # Footer: "Prepared by <brand>" centred in the bottom margin.
        if name:
            text = f'Prepared by {name}'
            font = _font_for(text)
            c.setFont(font, 7)
            c.setFillColor(colors.HexColor('#64748b'))
            c.drawCentredString(width / 2, 9, text)
            tw = stringWidth(text, font, 7)
            c.setStrokeColor(accent)
            c.setLineWidth(0.6)
            c.line(width / 2 - tw / 2, 17, width / 2 + tw / 2, 17)
        c.save()
        overlay = PdfReader(io.BytesIO(layer.getvalue())).pages[0]
        page.merge_page(overlay)
    metadata = {k: v for k, v in (reader.metadata or {}).items() if isinstance(v, str)}
    metadata['/Producer'] = ''                     # like the unbranded file: no generator tag
    writer.add_metadata(metadata)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def brand_docx(docx: bytes, branding: Branding) -> bytes:
    """Return a copy of the Word file with the branding in its header and footer."""
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt, RGBColor

    accent = RGBColor.from_string((branding.accent_color or DEFAULT_ACCENT)[1:].upper())
    doc = Document(io.BytesIO(docx))
    for section in doc.sections:
        section.header_distance = section.footer_distance = Pt(18)
        header = section.header.paragraphs[0]
        header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        if branding.logo:
            header.add_run().add_picture(io.BytesIO(branding.logo), height=Pt(18))
        elif branding.brand_name:
            run = header.add_run(branding.brand_name)
            run.font.size, run.font.color.rgb, run.bold = Pt(9), accent, True
        # Accent rule under the header.
        border = OxmlElement('w:pBdr')
        bottom = OxmlElement('w:bottom')
        for key, value in (('w:val', 'single'), ('w:sz', '8'), ('w:space', '4'), ('w:color', str(accent))):
            bottom.set(qn(key), value)
        border.append(bottom)
        header._p.get_or_add_pPr().append(border)
        if branding.brand_name:
            footer = section.footer.paragraphs[0]
            footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = footer.add_run(f'Prepared by {branding.brand_name}')
            run.font.size, run.font.color.rgb = Pt(8), RGBColor(0x64, 0x74, 0x8B)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()
