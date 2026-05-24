"""
Professional Resume PDF Generator
Creates clean, recruiter-friendly resumes that preserve the user's content.
"""

from reportlab.lib.pagesizes import LETTER
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from io import BytesIO
import textwrap

# ─── Page Setup ───────────────────────────────────────────────────────────────
W, H = LETTER
ML, MR = 50, 50  # Margins
MT, MB = 40, 50
TW = W - ML - MR

# ─── Professional Color Palette ───────────────────────────────────────────────
NAVY = colors.HexColor("#1e293b")       # Header background
WHITE = colors.white
DARK = colors.HexColor("#1e293b")       # Primary text
GRAY = colors.HexColor("#475569")       # Secondary text
LIGHT_GRAY = colors.HexColor("#64748b") # Tertiary text
ACCENT = colors.HexColor("#0f766e")     # Accent color (teal)


def _wrap(text: str, chars: int) -> list:
    """Wrap text to specified character width."""
    return textwrap.wrap(str(text).strip(), width=max(chars, 20)) or [""]


def _clean(text: str) -> str:
    """Clean bullet prefixes."""
    return text.lstrip("•-*–▸● ").strip()


class ResumeBuilder:
    """Builds professional PDF resumes."""

    def __init__(self, buf: BytesIO):
        self.c = canvas.Canvas(buf, pagesize=LETTER)
        self.y = H - MT
        self.page = 1

    def _footer(self):
        self.c.setFont("Helvetica", 8)
        self.c.setFillColor(LIGHT_GRAY)
        self.c.drawCentredString(W / 2, 25, f"Page {self.page}")

    def _new_page_if_needed(self, space: int = 50):
        if self.y < space + MB:
            self._footer()
            self.c.showPage()
            self.page += 1
            self.y = H - MT

    def header(self, name: str, contact: str):
        """Professional header with name and contact."""
        c = self.c
        
        # Header background
        c.setFillColor(NAVY)
        c.rect(0, H - 80, W, 80, fill=True, stroke=False)

        # Accent line
        c.setFillColor(ACCENT)
        c.rect(0, H - 80, W, 3, fill=True, stroke=False)

        # Name
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 22)
        c.drawCentredString(W / 2, H - 40, (name or "").upper())

        # Contact
        if contact:
            c.setFont("Helvetica", 9)
            c.setFillColor(colors.HexColor("#cbd5e1"))
            
            # Handle long contact info
            if len(contact) > 85:
                parts = contact.split("  |  ")
                mid = len(parts) // 2
                c.drawCentredString(W / 2, H - 55, "  |  ".join(parts[:mid]))
                c.drawCentredString(W / 2, H - 67, "  |  ".join(parts[mid:]))
            else:
                c.drawCentredString(W / 2, H - 58, contact)

        self.y = H - 95

    def section(self, title: str):
        """Section header with accent bar."""
        self._new_page_if_needed(45)
        c = self.c
        
        self.y -= 12

        # Accent bar
        c.setFillColor(ACCENT)
        c.rect(ML, self.y - 1, 3, 12, fill=True, stroke=False)

        # Title
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(DARK)
        c.drawString(ML + 8, self.y, title.upper())

        self.y -= 16

    def summary(self, text: str):
        """Professional summary paragraph."""
        if not text:
            return
            
        self.section("Professional Summary")
        c = self.c
        
        c.setFont("Helvetica", 10)
        c.setFillColor(GRAY)
        
        for line in _wrap(text, int(TW / 5)):
            self._new_page_if_needed(14)
            c.drawString(ML, self.y, line)
            self.y -= 13

        self.y -= 5

    def experience(self, jobs: list):
        """Work experience section."""
        if not jobs:
            return
            
        self.section("Professional Experience")
        c = self.c

        for job in jobs:
            self._new_page_if_needed(60)

            title = (job.get("title") or "").strip()
            company = (job.get("company") or "").strip()
            dates = (job.get("dates") or "").strip()
            location = (job.get("location") or "").strip()
            bullets = job.get("bullets") or []

            # Job title
            c.setFont("Helvetica-Bold", 10)
            c.setFillColor(DARK)
            c.drawString(ML, self.y, title)

            # Dates (right aligned)
            if dates:
                c.setFont("Helvetica", 9)
                c.setFillColor(LIGHT_GRAY)
                c.drawRightString(W - MR, self.y, dates)

            self.y -= 13

            # Company and location
            if company or location:
                c.setFont("Helvetica", 9)
                c.setFillColor(ACCENT)
                line = company
                if location:
                    line += f"  •  {location}" if company else location
                c.drawString(ML, self.y, line)
                self.y -= 13

            # Bullets
            for bullet in bullets[:6]:
                clean = _clean(bullet)
                if len(clean) < 8:
                    continue

                self._new_page_if_needed(14)
                c.setFont("Helvetica", 9)
                c.setFillColor(GRAY)

                lines = _wrap(clean, int((TW - 12) / 4.8))
                for i, ln in enumerate(lines):
                    prefix = "•  " if i == 0 else "    "
                    c.drawString(ML + 6, self.y, prefix + ln)
                    self.y -= 12

            self.y -= 8

    def skills(self, skill_list: list):
        """Skills section."""
        if not skill_list:
            return
            
        self.section("Skills")
        c = self.c

        # Clean and dedupe
        clean = []
        seen = set()
        for s in skill_list:
            s = str(s).strip()
            if s and len(s) < 40 and s.lower() not in seen:
                clean.append(s)
                seen.add(s.lower())

        # Render in rows
        c.setFont("Helvetica", 9)
        c.setFillColor(GRAY)

        row = []
        row_width = 0
        max_width = TW - 10

        for skill in clean[:30]:
            skill_w = c.stringWidth(skill, "Helvetica", 9) + 18
            
            if row_width + skill_w > max_width and row:
                self._new_page_if_needed(14)
                c.drawString(ML, self.y, "  •  ".join(row))
                self.y -= 13
                row = []
                row_width = 0

            row.append(skill)
            row_width += skill_w

        if row:
            self._new_page_if_needed(14)
            c.drawString(ML, self.y, "  •  ".join(row))
            self.y -= 13

        self.y -= 5

    def education(self, edu_list: list):
        """Education section."""
        if not edu_list:
            return
            
        self.section("Education")
        c = self.c

        for edu in edu_list:
            self._new_page_if_needed(30)

            degree = (edu.get("degree") or "").strip()
            school = (edu.get("school") or "").strip()
            year = (edu.get("year") or "").strip()

            if not degree and not school:
                continue

            # Degree
            if degree:
                c.setFont("Helvetica-Bold", 9)
                c.setFillColor(DARK)
                c.drawString(ML, self.y, degree)
                
                if year:
                    c.setFont("Helvetica", 9)
                    c.setFillColor(LIGHT_GRAY)
                    c.drawRightString(W - MR, self.y, year)
                
                self.y -= 12

            # School
            if school:
                c.setFont("Helvetica", 9)
                c.setFillColor(GRAY)
                c.drawString(ML, self.y, school)
                self.y -= 12

            self.y -= 4

    def certifications(self, cert_list: list):
        """Certifications section."""
        if not cert_list:
            return
            
        self.section("Certifications")
        c = self.c

        for cert in cert_list[:6]:
            clean = _clean(str(cert))
            if len(clean) < 3:
                continue

            self._new_page_if_needed(14)
            c.setFont("Helvetica", 9)
            c.setFillColor(GRAY)
            c.drawString(ML + 6, self.y, f"•  {clean}")
            self.y -= 12

        self.y -= 4

    def projects(self, project_list: list):
        """Projects section."""
        if not project_list:
            return
            
        self.section("Projects")
        c = self.c

        for proj in project_list[:4]:
            self._new_page_if_needed(35)

            name = (proj.get("name") or proj.get("title") or "").strip()
            desc = (proj.get("description") or "").strip()

            if not name:
                continue

            # Project name
            c.setFont("Helvetica-Bold", 9)
            c.setFillColor(DARK)
            c.drawString(ML, self.y, name)
            self.y -= 12

            # Description
            if desc:
                c.setFont("Helvetica", 9)
                c.setFillColor(GRAY)
                for line in _wrap(desc, int((TW - 8) / 4.8))[:2]:
                    self._new_page_if_needed(12)
                    c.drawString(ML + 6, self.y, line)
                    self.y -= 11

            self.y -= 5

    def save(self):
        self._footer()
        self.c.save()


# ─── Main Entry Point ─────────────────────────────────────────────────────────

def generate_optimized_resume(
    filename: str,
    score: float,
    improvements: list,
    resume_text: str = "",
    task_id: str = "",
    structured: dict | None = None,
) -> BytesIO:
    """
    Generates a professional, clean resume PDF.
    
    The resume preserves the user's original content while presenting it
    in a professional format that recruiters love.
    """
    buf = BytesIO()
    s = structured or {}

    # Extract data
    name = (s.get("name") or _get_name(resume_text) or "").strip()
    contact = (s.get("contact") or "").strip()
    summary = (s.get("summary") or "").strip()
    experience = s.get("experience") or []
    skills = s.get("skills") or []
    education = s.get("education") or []
    certifications = s.get("certifications") or []
    projects = s.get("projects") or []

    # Build PDF
    pdf = ResumeBuilder(buf)
    
    pdf.header(name, contact)
    pdf.summary(summary)
    pdf.experience(experience)
    pdf.skills(skills)
    pdf.education(education)
    pdf.certifications(certifications)
    pdf.projects(projects)
    
    pdf.save()
    buf.seek(0)
    return buf


def _get_name(text: str) -> str:
    """Extract name from resume text."""
    for line in (text or "").split("\n"):
        line = line.strip()
        if line and len(line) < 50 and not any(c in line for c in ["@", "http", "+", "|"]):
            return line
    return ""
