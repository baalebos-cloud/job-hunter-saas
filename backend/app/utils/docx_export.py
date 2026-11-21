"""Word (.docx) copy of a tailored resume.

Built from the same normalised resume data as the PDF, with the same regional
rules, in a plain single-column layout that applicant tracking systems parse
reliably: real headings, real bullet lists, no tables or text boxes.
"""
from __future__ import annotations

from io import BytesIO

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

from backend.app.utils.pdf_generator import apply_region_rules, normalize_resume_data

FONT = "Calibri"
DARK = RGBColor(0x1F, 0x29, 0x37)


def _rule(paragraph):
    """Thin line under a section heading."""
    border = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    for key, value in (("w:val", "single"), ("w:sz", "6"), ("w:space", "1"), ("w:color", "94A3B8")):
        bottom.set(qn(key), value)
    border.append(bottom)
    paragraph._p.get_or_add_pPr().append(border)


def _para(doc, text="", *, size=10.5, bold=False, align=None, space_after=2, color=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(0)
    if align:
        p.alignment = align
    if text:
        run = p.add_run(text)
        run.bold, run.font.size = bold, Pt(size)
        if color:
            run.font.color.rgb = color
    return p


def _heading(doc, text):
    p = _para(doc, text.upper(), size=11, bold=True, space_after=3, color=DARK)
    p.paragraph_format.space_before = Pt(8)
    _rule(p)


def _two_sided(doc, left, right, bold=True):
    """'Role — Company ........ Dates' using a right-aligned tab stop."""
    p = _para(doc, space_after=1)
    section = doc.sections[0]
    width = section.page_width - section.left_margin - section.right_margin
    p.paragraph_format.tab_stops.add_tab_stop(width, alignment=2)   # right
    run = p.add_run(left)
    run.bold, run.font.size = bold, Pt(10.5)
    if right:
        tail = p.add_run(f"\t{right}")
        tail.bold, tail.font.size = bold, Pt(10.5)
    return p


def _bullets(doc, items):
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(1)
        run = p.add_run(item)
        run.font.size = Pt(10.5)


def build_docx(raw: dict, region: str | None = None) -> bytes:
    data = apply_region_rules(normalize_resume_data(raw), region or "OTHER")
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name, style.font.size = FONT, Pt(10.5)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    for section in doc.sections:
        section.top_margin = section.bottom_margin = Pt(42)
        section.left_margin = section.right_margin = Pt(48)

    _para(doc, data["name"].upper(), size=20, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=1, color=DARK)
    subtitle = " · ".join(p for p in (data.get("title"), *[c.strip() for c in data.get("contact", "").split("|")]) if p)
    if subtitle:
        _para(doc, subtitle, size=10, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=6)

    if data.get("summary"):
        _heading(doc, "Professional Summary")
        _para(doc, data["summary"])
    if data.get("skills"):
        _heading(doc, "Skills")
        for category, items in data["skills"].items():
            p = _para(doc, space_after=1)
            if category and category.lower() not in ("skills", "general", "other"):
                label = p.add_run(f"{category}: ")
                label.bold = True
            p.add_run(", ".join(items))
    if data.get("experience"):
        _heading(doc, "Experience")
        for job in data["experience"]:
            _two_sided(doc, " — ".join(p for p in (job["role"], job["company"]) if p), job["dates"])
            if job.get("location"):
                _para(doc, job["location"], size=10, space_after=1)
            _bullets(doc, job["bullets"])
            if job.get("environment"):
                _para(doc, f"Environment: {job['environment']}", size=10, space_after=3)
    if data.get("projects"):
        _heading(doc, "Projects")
        for project in data["projects"]:
            _two_sided(doc, " — ".join(p for p in (project["title"], project["subtitle"]) if p), project.get("tech", ""),
                       bold=True)
            _bullets(doc, project["bullets"])
    if data.get("education"):
        _heading(doc, "Education")
        for school in data["education"]:
            _two_sided(doc, " — ".join(p for p in (school["degree"], school["institution"]) if p), school["year"], bold=False)
    if data.get("certifications"):
        _heading(doc, "Certifications")
        _bullets(doc, data["certifications"])
    if data.get("additional_information"):
        _heading(doc, "Additional Information")
        for line in data["additional_information"].splitlines():
            _para(doc, line)

    doc.core_properties.author = data["name"]
    doc.core_properties.title = f"{data['name']} — Resume"
    out = BytesIO()
    doc.save(out)
    return out.getvalue()
