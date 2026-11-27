"""Word (.docx) copy of a tailored resume.

Built from the same normalised resume data as the PDF, with the same regional
rules, page size, section headings, order and condensing, in a plain
single-column layout that applicant tracking systems parse reliably: real
headings, real bullet lists, no tables or text boxes.
"""
from __future__ import annotations

from io import BytesIO

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Mm, Pt, RGBColor

from backend.app.utils.pdf_generator import (LETTER_REGIONS, _bullet_markup, _split_skills, apply_region_rules,
                                             normalize_resume_data, resolve_region)

FONT = "Calibri"
ACCENT = RGBColor(0x1F, 0x4E, 0x79)     # same as the PDF: name, headings and rules
TEXT = RGBColor(0x1A, 0x1A, 0x1A)
MUTED = RGBColor(0x55, 0x55, 0x55)
SIZE = 10.5
PAGE_SIZES = {"A4": (Mm(210), Mm(297)), "LETTER": (Inches(8.5), Inches(11))}
# The PDF's section headings, in the PDF's order.
HEADINGS = ("Professional Summary", "Core Skills", "Professional Experience", "Selected Projects",
            "Certifications", "Education", "Additional Information")


def _rule(paragraph):
    """Line under a section heading, in the accent colour."""
    border = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    for key, value in (("w:val", "single"), ("w:sz", "8"), ("w:space", "1"), ("w:color", "1F4E79")):
        bottom.set(qn(key), value)
    border.append(bottom)
    paragraph._p.get_or_add_pPr().append(border)


def _run(p, text, *, bold=False, italic=False, color=TEXT, size=SIZE):
    run = p.add_run(text)
    run.bold, run.italic, run.font.size = bold, italic, Pt(size)
    run.font.color.rgb = color
    return run


def _para(doc, text="", *, size=SIZE, bold=False, italic=False, align=None, space_after=2, color=TEXT):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(0)
    if align is not None:
        p.alignment = align
    if text:
        _run(p, text, bold=bold, italic=italic, color=color, size=size)
    return p


def _heading(doc, text, upper=True):
    p = _para(doc, text.upper() if upper else text, size=11, bold=True, space_after=3, color=ACCENT)
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.keep_with_next = True
    _rule(p)


def _entry(doc, primary, secondary, right):
    """Bold title, muted "| organisation", muted italic date on a right tab, as in the PDF."""
    p = _para(doc, space_after=1)
    p.paragraph_format.keep_with_next = True
    section = doc.sections[0]
    width = section.page_width - section.left_margin - section.right_margin
    p.paragraph_format.tab_stops.add_tab_stop(width, alignment=2)   # right
    if primary:
        _run(p, primary, bold=True)
    if secondary:
        _run(p, ("  |  " if primary else "") + secondary, color=MUTED)
    if right:
        _run(p, f"\t{right}", italic=True, color=MUTED)
    return p


def _bullets(doc, items, labels=True):
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(1)
        head, sep, tail = item.partition(": ")
        if labels and _bullet_markup(item).startswith("<b>"):     # "Label: sentence" lead-in, as in the PDF
            _run(p, f"{head}:", bold=True)
            _run(p, f" {tail}")
        else:
            _run(p, item)


def page_size_name(region: str | None, page_size: str | None = None) -> str:
    if page_size and page_size.strip().upper() in PAGE_SIZES:
        return page_size.strip().upper()
    return "LETTER" if resolve_region(region) in LETTER_REGIONS else "A4"


def build_docx(raw: dict, region: str | None = None, page_size: str | None = None, template: str | None = None) -> bytes:
    """``raw`` should be the content the PDF used (``ExportResult.content``) so both match."""
    from backend.app.utils.pdf_generator import resolve_template
    template = resolve_template(template)
    data = apply_region_rules(normalize_resume_data(raw), region or "OTHER")
    doc = Document()
    width, height = PAGE_SIZES[page_size_name(region, page_size)]
    margin = Pt(24 if template == "compact" else 36)
    for section in doc.sections:
        section.page_width, section.page_height = width, height
        section.top_margin = section.bottom_margin = margin
        section.left_margin = section.right_margin = margin
    style = doc.styles["Normal"]
    style.font.name, style.font.size = FONT, Pt(9.5 if template == "compact" else SIZE)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    header = WD_ALIGN_PARAGRAPH.LEFT if template == "modern" else WD_ALIGN_PARAGRAPH.CENTER
    upper = template != "modern"
    heading = lambda doc, text: _heading(doc, text, upper)  # noqa: E731

    summary, skills, experience, projects, certifications, education, additional = HEADINGS
    _para(doc, data["name"], size=18, bold=True, align=header, space_after=1, color=ACCENT)
    if data.get("title"):
        _para(doc, data["title"], align=header, space_after=1, color=MUTED)
    if data.get("contact"):
        _para(doc, data["contact"], align=header, space_after=6, color=MUTED)

    if data.get("summary"):
        heading(doc, summary)
        _para(doc, data["summary"])
    if data.get("skills"):
        heading(doc, skills)
        for category, items in data["skills"].items():
            p = _para(doc, space_after=1)
            if not (category == "Skills" and len(data["skills"]) == 1):
                _run(p, f"{category}: ", bold=True)
            _run(p, ", ".join(items))
    if data.get("experience"):
        heading(doc, experience)
        for job in data["experience"]:
            _entry(doc, job["role"], " · ".join(p for p in (job["company"], job.get("location")) if p), job["dates"])
            _bullets(doc, job["bullets"])
            if job.get("environment"):
                p = _para(doc, space_after=3)
                _run(p, "Tools: ", bold=True)
                _run(p, " · ".join(_split_skills(job["environment"])))
    if data.get("projects"):
        heading(doc, projects)
        for project in data["projects"]:
            _entry(doc, project["title"], project.get("subtitle", ""), "")
            if project.get("tech"):
                _para(doc, " · ".join(_split_skills(project["tech"])), italic=True, color=MUTED, space_after=1)
            _bullets(doc, project["bullets"])
    if data.get("certifications"):
        heading(doc, certifications)
        _bullets(doc, data["certifications"], labels=False)
    if data.get("education"):
        heading(doc, education)
        for school in data["education"]:
            _entry(doc, school["degree"], " · ".join(p for p in (school["institution"], school.get("location")) if p),
                   school["year"])
    if data.get("additional_information"):
        heading(doc, additional)
        for line in data["additional_information"].splitlines():
            _para(doc, line)

    doc.core_properties.author = data["name"]
    doc.core_properties.title = f"{data['name']} - Resume"
    out = BytesIO()
    doc.save(out)
    return out.getvalue()
