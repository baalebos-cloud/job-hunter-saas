"""
Professional Resume PDF Generator
Creates clean, recruiter-friendly resumes that preserve the user's content.
"""

from reportlab.lib.pagesizes import LETTER
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from io import BytesIO


# ─── Colors ───────────────────────────────────────────────────────────────────
DARK_SLATE    = colors.HexColor("#0f172a")
EMERALD       = colors.HexColor("#10b981")
LIGHT_EMERALD = colors.HexColor("#ecfdf5")
SLATE_600     = colors.HexColor("#475569")
SLATE_400     = colors.HexColor("#94a3b8")
SLATE_200     = colors.HexColor("#e2e8f0")
WHITE         = colors.white


# ─── Styles ───────────────────────────────────────────────────────────────────
def build_styles():
    return {
        "name": ParagraphStyle(
            "name", fontName="Helvetica-Bold", fontSize=22,
            textColor=DARK_SLATE, spaceAfter=2, leading=26, alignment=TA_CENTER,
        ),
        "title": ParagraphStyle(
            "title", fontName="Helvetica", fontSize=11,
            textColor=EMERALD, spaceAfter=4, leading=14, alignment=TA_CENTER,
        ),
        "contact": ParagraphStyle(
            "contact", fontName="Helvetica", fontSize=8.5,
            textColor=SLATE_600, spaceAfter=2, leading=12, alignment=TA_CENTER,
        ),
        "section_header": ParagraphStyle(
            "section_header", fontName="Helvetica-Bold", fontSize=9,
            textColor=DARK_SLATE, spaceBefore=10, spaceAfter=3,
            leading=12, alignment=TA_LEFT,
        ),
        "job_title": ParagraphStyle(
            "job_title", fontName="Helvetica-Bold", fontSize=10,
            textColor=DARK_SLATE, spaceAfter=1, leading=13,
        ),
        "company": ParagraphStyle(
            "company", fontName="Helvetica", fontSize=9.5,
            textColor=EMERALD, spaceAfter=1, leading=12,
        ),
        "date": ParagraphStyle(
            "date", fontName="Helvetica-Oblique", fontSize=8.5,
            textColor=SLATE_400, spaceAfter=3, leading=11,
        ),
        "bullet": ParagraphStyle(
            "bullet", fontName="Helvetica", fontSize=9,
            textColor=SLATE_600, spaceAfter=2, leading=13, leftIndent=12,
        ),
        "body": ParagraphStyle(
            "body", fontName="Helvetica", fontSize=9,
            textColor=SLATE_600, spaceAfter=3, leading=13,
        ),
        "skill_value": ParagraphStyle(
            "skill_value", fontName="Helvetica", fontSize=8.5,
            textColor=SLATE_600, spaceAfter=3, leading=12,
        ),
        "suggestion": ParagraphStyle(
            "suggestion", fontName="Helvetica-Oblique", fontSize=8.5,
            textColor=SLATE_600, spaceAfter=3, leading=13, leftIndent=12,
        ),
        "footer": ParagraphStyle(
            "footer", fontName="Helvetica", fontSize=7.5,
            textColor=SLATE_400, alignment=TA_CENTER,
        ),
        "tag": ParagraphStyle(
            "tag", fontName="Helvetica-Bold", fontSize=7.5,
            textColor=WHITE, alignment=TA_CENTER,
        ),
        "score": ParagraphStyle(
            "score", fontName="Helvetica-Bold", fontSize=18,
            textColor=EMERALD, alignment=TA_CENTER,
        ),
        "ats_label": ParagraphStyle(
            "ats_label", fontName="Helvetica-Bold", fontSize=8,
            textColor=EMERALD, alignment=TA_CENTER,
        ),
    }


# ─── Helpers ──────────────────────────────────────────────────────────────────
def section_divider(styles, title):
    return [
        Spacer(1, 6),
        Paragraph(title.upper(), styles["section_header"]),
        HRFlowable(width="100%", thickness=1.5, color=EMERALD, spaceAfter=5),
    ]


def build_ats_badge(score, styles):
    color = EMERALD if score >= 80 else colors.HexColor("#f59e0b") if score >= 60 else colors.HexColor("#ef4444")
    label = "Strong Fit" if score >= 80 else "Good Fit" if score >= 60 else "Needs Work"

    badge_data = [[
        Paragraph("ATS MATCH SCORE", styles["ats_label"]),
        Paragraph(f"<b>{round(score)}%</b>", ParagraphStyle(
            "sc", fontName="Helvetica-Bold", fontSize=18,
            textColor=color, alignment=TA_CENTER
        )),
        Paragraph(label, ParagraphStyle(
            "lb", fontName="Helvetica-Bold", fontSize=9,
            textColor=color, alignment=TA_CENTER
        )),
    ]]
    t = Table(badge_data, colWidths=[2*inch, 1.5*inch, 1.5*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_EMERALD),
        ("BOX", (0, 0), (-1, -1), 1, color),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def build_skill_tag(skill, styles):
    tag_data = [[Paragraph(f"  {skill.upper()}  ", styles["tag"])]]
    t = Table(tag_data, colWidths=[1.4*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), EMERALD),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


# ─── Main Generator ───────────────────────────────────────────────────────────
def generate_optimized_resume(
    filename: str,
    score: float,
    improvements: list,
    resume_data: dict = None,
    resume_text: str = None,
    task_id: str = None,
    structured: dict = None,
) -> BytesIO:
    """
    Generates a professional resume PDF styled like the user's original resume.

    Args:
        filename: Original resume filename
        score: ATS match score 0-100
        improvements: List of {"skill": str, "bullet_point": str}
        resume_data: Structured resume dict from extract_resume_data()
        resume_text: Plain text of the resume for reference (optional)
        task_id: Task/resume ID for tracking (optional)
        structured: Structured resume data from rewrite_resume_for_job() (optional)

    Returns:
        BytesIO PDF buffer
    """
    buffer = BytesIO()
    styles = build_styles()
    data = structured or resume_data or {}

    # Fallback name from filename
    name = data.get("name") or (
        filename.replace(".pdf", "").replace(".docx", "")
        .replace("_", " ").replace("-", " ").title()
    )

    doc = SimpleDocTemplate(
        buffer, pagesize=LETTER,
        leftMargin=0.6*inch, rightMargin=0.6*inch,
        topMargin=0.5*inch, bottomMargin=0.5*inch,
    )

    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    story.append(Paragraph(name.upper(), styles["name"]))
    if data.get("title"):
        story.append(Paragraph(data["title"], styles["title"]))
    if data.get("contact"):
        story.append(Paragraph(data["contact"], styles["contact"]))
    story.append(Spacer(1, 8))

    # ── ATS Badge ─────────────────────────────────────────────────────────────
    story.append(build_ats_badge(score, styles))
    story.append(Spacer(1, 10))

    # ── Professional Summary ──────────────────────────────────────────────────
    if data.get("summary"):
        story.extend(section_divider(styles, "Professional Summary"))
        story.append(Paragraph(data["summary"], styles["body"]))

    # ── Experience ────────────────────────────────────────────────────────────
    if data.get("experience"):
        story.extend(section_divider(styles, "Professional Experience"))
        for exp in data["experience"]:
            story.append(Paragraph(exp.get("role", ""), styles["job_title"]))
            company_line = exp.get("company", "")
            if exp.get("location"):
                company_line += f"   |   {exp['location']}"
            story.append(Paragraph(company_line, styles["company"]))
            if exp.get("dates"):
                story.append(Paragraph(exp["dates"], styles["date"]))
            for bullet in exp.get("bullets", []):
                story.append(Paragraph(f"• {bullet}", styles["bullet"]))
            story.append(Spacer(1, 4))

    # ── Core Competencies ─────────────────────────────────────────────────────
    if data.get("skills"):
        story.extend(section_divider(styles, "Core Competencies"))
        for category, items in data["skills"].items():
            items_str = ", ".join(items) if isinstance(items, list) else str(items)
            story.append(Paragraph(
                f"<b>{category}:</b>  {items_str}",
                styles["skill_value"]
            ))

    # ── AI-Suggested Improvements ─────────────────────────────────────────────
    if improvements:
        story.extend(section_divider(styles, "AI-Suggested Resume Improvements"))
        story.append(Paragraph(
            "The following bullet points were generated by Baalebos AI to close the gap "
            "between your resume and the target job description. Add the most relevant "
            "ones to improve your ATS score.",
            styles["body"]
        ))
        story.append(Spacer(1, 4))

        for imp in improvements[:8]:
            skill = imp.get("skill", "Improvement")
            bullet = imp.get("bullet_point", "")
            story.append(build_skill_tag(skill, styles))
            story.append(Paragraph(f'• "{bullet}"', styles["suggestion"]))
            story.append(Spacer(1, 3))

    # ── Missing Keywords ──────────────────────────────────────────────────────
    missing = data.get("missing_keywords", [])
    if not missing and improvements:
        missing = [imp.get("skill", "") for imp in improvements if imp.get("skill")]

    if missing:
        story.extend(section_divider(styles, "Missing Keywords to Add"))
        story.append(Paragraph(
            "  •  ".join([k for k in missing if k][:15]),
            styles["body"]
        ))

    # ── Education ─────────────────────────────────────────────────────────────
    if data.get("education"):
        story.extend(section_divider(styles, "Education"))
        for edu in data["education"]:
            story.append(Paragraph(f"<b>{edu.get('degree', '')}</b>", styles["job_title"]))
            institution = edu.get("institution", "")
            if edu.get("year"):
                institution += f"   |   {edu['year']}"
            story.append(Paragraph(institution, styles["company"]))

    # ── Certifications ────────────────────────────────────────────────────────
    if data.get("certifications"):
        story.extend(section_divider(styles, "Certifications"))
        for cert in data["certifications"]:
            story.append(Paragraph(f"• {cert}", styles["bullet"]))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5, color=SLATE_200))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Generated by Baalebos Cloud AI  •  baalebo.xyz  •  AI-Powered Career Infrastructure",
        styles["footer"]
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer
