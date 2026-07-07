from reportlab.lib.pagesizes import LETTER
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
    Table, TableStyle, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from io import BytesIO


# ─── Colors ───────────────────────────────────────────────────────────────────
DARK_SLATE = colors.HexColor("#0f172a")
EMERALD    = colors.HexColor("#10b981")
SLATE_600  = colors.HexColor("#475569")
SLATE_400  = colors.HexColor("#94a3b8")
SLATE_200  = colors.HexColor("#e2e8f0")


# ─── Styles ───────────────────────────────────────────────────────────────────
def build_styles():
    return {
        "name": ParagraphStyle(
            "name", fontName="Helvetica-Bold", fontSize=20,
            textColor=DARK_SLATE, spaceAfter=3, leading=24, alignment=TA_CENTER,
        ),
        "tagline": ParagraphStyle(
            "tagline", fontName="Helvetica", fontSize=10,
            textColor=EMERALD, spaceAfter=3, leading=14, alignment=TA_CENTER,
        ),
        "contact": ParagraphStyle(
            "contact", fontName="Helvetica", fontSize=8.5,
            textColor=SLATE_600, spaceAfter=2, leading=12, alignment=TA_CENTER,
        ),
        "section_header": ParagraphStyle(
            "section_header", fontName="Helvetica-Bold", fontSize=9,
            textColor=DARK_SLATE, spaceBefore=8, spaceAfter=2,
            leading=12, alignment=TA_LEFT,
        ),
        "job_title": ParagraphStyle(
            "job_title", fontName="Helvetica-Bold", fontSize=9.5,
            textColor=DARK_SLATE, spaceAfter=1, leading=13,
        ),
        "company_date": ParagraphStyle(
            "company_date", fontName="Helvetica-Oblique", fontSize=8.5,
            textColor=SLATE_400, spaceAfter=3, leading=11,
        ),
        "bullet": ParagraphStyle(
            "bullet", fontName="Helvetica", fontSize=8.5,
            textColor=SLATE_600, spaceAfter=2, leading=12, leftIndent=10,
        ),
        "env_line": ParagraphStyle(
            "env_line", fontName="Helvetica-Oblique", fontSize=8,
            textColor=SLATE_400, spaceAfter=4, leading=11, leftIndent=10,
        ),
        "body": ParagraphStyle(
            "body", fontName="Helvetica", fontSize=8.5,
            textColor=SLATE_600, spaceAfter=3, leading=12,
        ),
        "skill_key": ParagraphStyle(
            "skill_key", fontName="Helvetica-Bold", fontSize=8,
            textColor=DARK_SLATE, spaceAfter=0, leading=11,
        ),
        "skill_val": ParagraphStyle(
            "skill_val", fontName="Helvetica", fontSize=8,
            textColor=SLATE_600, spaceAfter=0, leading=11,
        ),
        "project_title": ParagraphStyle(
            "project_title", fontName="Helvetica-Bold", fontSize=9,
            textColor=DARK_SLATE, spaceAfter=1, leading=12,
        ),
        "cert": ParagraphStyle(
            "cert", fontName="Helvetica", fontSize=8.5,
            textColor=SLATE_600, spaceAfter=2, leading=12, leftIndent=10,
        ),
        "footer": ParagraphStyle(
            "footer", fontName="Helvetica", fontSize=7.5,
            textColor=SLATE_400, alignment=TA_CENTER,
        ),
    }


# ─── Section Divider ──────────────────────────────────────────────────────────
def section_divider(title, styles):
    return [
        Paragraph(title.upper(), styles["section_header"]),
        HRFlowable(width="100%", thickness=1.2, color=EMERALD, spaceAfter=4),
    ]


# ─── Two-Column Skills Table ───────────────────────────────────────────────────
def build_skills_table(skills: dict, styles):
    """
    Builds a two-column skills grid matching the resume style.
    Missing keywords are already merged into skills before calling this.
    """
    if not skills:
        return []

    items = list(skills.items())
    rows = []

    for i in range(0, len(items), 2):
        left_cat, left_vals = items[i]
        left_str = ", ".join(left_vals) if isinstance(left_vals, list) else str(left_vals)

        if i + 1 < len(items):
            right_cat, right_vals = items[i + 1]
            right_str = ", ".join(right_vals) if isinstance(right_vals, list) else str(right_vals)
        else:
            right_cat, right_str = "", ""

        left_cell = [
            Paragraph(f"<b>{left_cat}:</b>", styles["skill_key"]),
            Paragraph(left_str, styles["skill_val"]),
        ]
        right_cell = [
            Paragraph(f"<b>{right_cat}:</b>", styles["skill_key"]) if right_cat else Paragraph("", styles["skill_key"]),
            Paragraph(right_str, styles["skill_val"]) if right_str else Paragraph("", styles["skill_val"]),
        ]
        rows.append([left_cell, right_cell])

    t = Table(rows, colWidths=[3.5*inch, 3.5*inch])
    t.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 2),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return [t]


# ─── Merge Missing Keywords into Skills ───────────────────────────────────────
def merge_keywords_into_skills(skills: dict, missing_keywords: list) -> dict:
    """
    Weaves missing keywords into the most relevant skill category.
    This produces an improved, ATS-ready skills section for the owner.
    """
    if not missing_keywords or not skills:
        return skills

    merged = {k: list(v) if isinstance(v, list) else [v] for k, v in skills.items()}

    # Keyword-to-category mapping heuristics
    category_hints = {
        "terraform":       ["Infrastructure as Code", "IaC", "Automation"],
        "kubernetes":      ["Containers", "Container", "DevOps"],
        "helm":            ["Containers", "DevOps", "CI/CD"],
        "prometheus":      ["Monitoring", "Observability"],
        "grafana":         ["Monitoring", "Observability"],
        "ansible":         ["Infrastructure as Code", "Automation"],
        "ci/cd":           ["CI/CD", "DevOps"],
        "jenkins":         ["CI/CD", "DevOps"],
        "github actions":  ["CI/CD", "DevOps"],
        "docker":          ["Containers", "DevOps"],
        "python":          ["Scripting", "Scripting & Automation"],
        "bash":            ["Scripting", "Scripting & Automation"],
        "aws":             ["AWS Core Services", "Cloud"],
        "azure":           ["Other Clouds", "Cloud"],
        "gcp":             ["Other Clouds", "Cloud"],
        "linux":           ["Linux Administration", "Systems"],
        "security":        ["Networking & Security", "Security"],
        "datadog":         ["Monitoring", "Observability"],
    }

    skill_keys_lower = {k.lower(): k for k in merged.keys()}

    for kw in missing_keywords:
        if not kw or "API Key" in kw:
            continue

        kw_lower = kw.lower()
        placed = False

        # Try to find best matching category
        for hint_kw, hint_cats in category_hints.items():
            if hint_kw in kw_lower:
                for cat in hint_cats:
                    cat_lower = cat.lower()
                    if cat_lower in skill_keys_lower:
                        real_key = skill_keys_lower[cat_lower]
                        if kw not in merged[real_key]:
                            merged[real_key].append(kw)
                        placed = True
                        break
            if placed:
                break

        # Fallback: add to first available category
        if not placed:
            first_key = list(merged.keys())[0]
            if kw not in merged[first_key]:
                merged[first_key].append(kw)

    return merged


# ─── Main Generator ───────────────────────────────────────────────────────────
def generate_optimized_resume(
    filename: str,
    score: float,
    improvements: list,
    resume_data: dict = None
) -> BytesIO:
    """
    Generates a clean, ready-to-use professional resume PDF.

    - No ATS badge — this is a real resume the owner can submit
    - Missing keywords are woven into the skills section naturally
    - AI-suggested bullet points added as additional experience bullets
    - Matches the two-column skills grid and environment line style

    Args:
        filename:     Original resume filename
        score:        ATS match score (used internally, not shown)
        improvements: List of {"skill": str, "bullet_point": str}
        resume_data:  Structured resume dict from extract_resume_data()

    Returns:
        BytesIO PDF buffer
    """
    buffer = BytesIO()
    styles = build_styles()
    data = resume_data or {}

    name = data.get("name") or (
        filename.replace(".pdf", "").replace(".docx", "")
        .replace("_", " ").replace("-", " ").title()
    )

    doc = SimpleDocTemplate(
        buffer, pagesize=LETTER,
        leftMargin=0.55*inch, rightMargin=0.55*inch,
        topMargin=0.45*inch, bottomMargin=0.45*inch,
    )

    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    story.append(Paragraph(name.upper(), styles["name"]))
    if data.get("title"):
        story.append(Paragraph(data["title"], styles["tagline"]))
    if data.get("contact"):
        story.append(Paragraph(data["contact"], styles["contact"]))
    story.append(Spacer(1, 8))

    # ── Professional Summary ──────────────────────────────────────────────────
    if data.get("summary"):
        story.extend(section_divider("Professional Summary", styles))
        story.append(Paragraph(data["summary"], styles["body"]))
        story.append(Spacer(1, 4))

    # ── Core Skills — with missing keywords merged in ─────────────────────────
    raw_skills = data.get("skills", {})
    missing_kws = data.get("missing_keywords", [])
    enriched_skills = merge_keywords_into_skills(raw_skills, missing_kws)

    if enriched_skills:
        story.extend(section_divider("Core AWS & Technical Skills", styles))
        story.extend(build_skills_table(enriched_skills, styles))
        story.append(Spacer(1, 4))

    # ── Professional Experience ───────────────────────────────────────────────
    if data.get("experience"):
        story.extend(section_divider("Professional Experience", styles))

        # Collect AI improvement bullets to inject into the first experience entry
        ai_bullets = [imp.get("bullet_point", "") for imp in improvements if imp.get("bullet_point")]

        for idx, exp in enumerate(data["experience"]):
            block = []
            block.append(Paragraph(exp.get("role", ""), styles["job_title"]))

            company = exp.get("company", "")
            dates   = exp.get("dates", "")
            if company and dates:
                block.append(Paragraph(f"{company}    {dates}", styles["company_date"]))
            elif company:
                block.append(Paragraph(company, styles["company_date"]))

            for bullet in exp.get("bullets", []):
                block.append(Paragraph(f"• {bullet}", styles["bullet"]))

            # Inject AI-suggested bullets into the most recent role
            if idx == 0 and ai_bullets:
                for ab in ai_bullets[:3]:
                    block.append(Paragraph(f"• {ab}", styles["bullet"]))

            if exp.get("environment"):
                env = exp["environment"] if isinstance(exp["environment"], str) else " · ".join(exp["environment"])
                block.append(Paragraph(f"Environment: {env}", styles["env_line"]))

            block.append(Spacer(1, 5))
            story.append(KeepTogether(block))

    # ── Selected Projects ─────────────────────────────────────────────────────
    if data.get("projects"):
        story.extend(section_divider("Selected Projects", styles))
        for proj in data["projects"]:
            block = []
            title = proj.get("title", "")
            tech  = proj.get("tech", "")
            label = f"{title} — <font color='#10b981'>{tech}</font>" if tech else title
            block.append(Paragraph(label, styles["project_title"]))
            for bullet in proj.get("bullets", []):
                block.append(Paragraph(f"• {bullet}", styles["bullet"]))
            block.append(Spacer(1, 4))
            story.append(KeepTogether(block))

    # ── Certifications ────────────────────────────────────────────────────────
    if data.get("certifications"):
        story.extend(section_divider("Certifications", styles))
        for cert in data["certifications"]:
            story.append(Paragraph(f"• {cert}", styles["cert"]))
        story.append(Spacer(1, 4))

    # ── Education ─────────────────────────────────────────────────────────────
    if data.get("education"):
        story.extend(section_divider("Education", styles))
        for edu in data["education"]:
            degree      = edu.get("degree", "")
            institution = edu.get("institution", "")
            year        = edu.get("year", "")
            line = f"<b>{degree}</b>"
            if institution:
                line += f" — {institution}"
            if year:
                line += f", {year}"
            story.append(Paragraph(line, styles["body"]))
        story.append(Spacer(1, 4))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.5, color=SLATE_200))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Optimized by Baalebos Cloud AI  •  baalebo.xyz",
        styles["footer"]
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer
