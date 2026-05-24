"""
Premium Resume PDF Generator — Recruiter-Grade Quality
Produces visually stunning, ATS-compliant resumes comparable to TopResume/Zety.

Features:
✅ Professional navy header band with white name
✅ ATS Score badge in header
✅ Clean section headers with accent bars
✅ Skill pills/badges in columns
✅ Proper typography hierarchy
✅ Elegant job entry formatting
✅ Page numbers and consistent spacing
✅ 100% ATS-compliant (standard fonts, single column, no images)
"""

from reportlab.lib.pagesizes import LETTER
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from io import BytesIO
import textwrap

# ─── Page Setup ───────────────────────────────────────────────────────────────
W, H = LETTER
ML, MR = 48, 48  # Left/right margins
MT, MB = 36, 48  # Top/bottom margins
TW = W - ML - MR  # Text width

# ─── Premium Color Palette ────────────────────────────────────────────────────
NAVY       = colors.HexColor("#0f172a")  # Header background
WHITE      = colors.white
SLATE_900  = colors.HexColor("#0f172a")  # Primary text
SLATE_700  = colors.HexColor("#334155")  # Secondary text
SLATE_500  = colors.HexColor("#64748b")  # Tertiary text
SLATE_300  = colors.HexColor("#cbd5e1")  # Light text on dark bg
EMERALD    = colors.HexColor("#059669")  # Accent color (company names, score badge)


def _wrap(text: str, chars: int) -> list:
    """Wrap text to specified character width."""
    return textwrap.wrap(str(text).strip(), width=max(chars, 20)) or [""]


def _clean_bullet(text: str) -> str:
    """Remove bullet prefixes and clean up text."""
    return text.lstrip("•-*–▸● ").strip()


class PremiumResume:
    """Premium resume canvas with professional styling."""

    def __init__(self, buf: BytesIO, score: float = 0):
        self.c = canvas.Canvas(buf, pagesize=LETTER)
        self.y = H - MT
        self.page = 1
        self.score = score

    def _page_footer(self):
        """Render page number footer."""
        self.c.setFont("Helvetica", 8)
        self.c.setFillColor(SLATE_500)
        self.c.drawCentredString(W / 2, 24, f"Page {self.page}")

    def _check_space(self, needed: int = 60):
        """Check if we need a new page."""
        if self.y < needed + MB:
            self._page_footer()
            self.c.showPage()
            self.page += 1
            self.y = H - MT

    def render_header(self, name: str, contact: str):
        """
        Render premium header with navy background band and ATS score badge.
        """
        c = self.c
        header_height = 85

        # Navy background band
        c.setFillColor(NAVY)
        c.rect(0, H - header_height, W, header_height, fill=True, stroke=False)

        # Emerald accent bar at bottom of header
        c.setFillColor(EMERALD)
        c.rect(0, H - header_height, W, 4, fill=True, stroke=False)

        # Name - centered, white, bold
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 24)
        name_clean = (name or "Candidate").strip().upper()
        c.drawCentredString(W / 2, H - 45, name_clean)

        # Contact info - centered, white, smaller
        if contact:
            c.setFont("Helvetica", 10)
            c.setFillColor(SLATE_300)
            # Truncate if too long, split into two lines if needed
            if len(contact) > 80:
                parts = contact.split("  |  ")
                mid = len(parts) // 2
                line1 = "  |  ".join(parts[:mid])
                line2 = "  |  ".join(parts[mid:])
                c.drawCentredString(W / 2, H - 62, line1)
                c.drawCentredString(W / 2, H - 75, line2)
            else:
                c.drawCentredString(W / 2, H - 65, contact)

        # ATS Score badge (top right corner)
        if self.score > 0:
            badge_x = W - MR - 60
            badge_y = H - 35
            badge_w, badge_h = 55, 22

            # Badge background
            c.setFillColor(EMERALD)
            c.roundRect(badge_x, badge_y, badge_w, badge_h, 4, fill=True, stroke=False)

            # Badge text
            c.setFillColor(WHITE)
            c.setFont("Helvetica-Bold", 9)
            c.drawCentredString(badge_x + badge_w/2, badge_y + 7, f"ATS {int(self.score)}%")

        self.y = H - header_height - 20

    def section_header(self, title: str):
        """Render elegant section header with left accent bar."""
        self._check_space(50)
        c = self.c

        self.y -= 8

        # Left accent bar
        c.setFillColor(EMERALD)
        c.rect(ML, self.y - 2, 3, 14, fill=True, stroke=False)

        # Section title
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(SLATE_900)
        c.drawString(ML + 10, self.y, title.upper())

        self.y -= 18

    def render_summary(self, summary: str):
        """Render professional summary with proper text wrapping."""
        if not summary or not summary.strip():
            return

        self.section_header("Professional Summary")
        c = self.c

        c.setFont("Helvetica", 10)
        c.setFillColor(SLATE_700)

        chars = int(TW / 5.2)
        for line in _wrap(summary, chars):
            self._check_space(16)
            c.drawString(ML, self.y, line)
            self.y -= 14

        self.y -= 6

    def render_experience(self, experience: list):
        """Render work experience with professional job entries."""
        if not experience:
            return

        self.section_header("Professional Experience")
        c = self.c

        for job in experience:
            self._check_space(70)

            title = (job.get("title") or "").strip()
            company = (job.get("company") or "").strip()
            dates = (job.get("dates") or "").strip()
            location = (job.get("location") or "").strip()
            bullets = job.get("bullets") or []

            # Job title (bold, dark)
            c.setFont("Helvetica-Bold", 11)
            c.setFillColor(SLATE_900)
            c.drawString(ML, self.y, title)

            # Dates (right-aligned, gray)
            if dates:
                c.setFont("Helvetica", 9)
                c.setFillColor(SLATE_500)
                c.drawRightString(W - MR, self.y, dates)

            self.y -= 14

            # Company and location
            if company or location:
                c.setFont("Helvetica", 10)
                c.setFillColor(EMERALD)
                company_line = company
                if location:
                    company_line += f"  •  {location}" if company else location
                c.drawString(ML, self.y, company_line)
                self.y -= 14

            # Bullets
            for bullet in bullets[:7]:  # Max 7 bullets per job
                clean = _clean_bullet(bullet)
                if not clean or len(clean) < 10:
                    continue

                self._check_space(16)
                c.setFont("Helvetica", 10)
                c.setFillColor(SLATE_700)

                # Wrap long bullets
                chars = int((TW - 15) / 5.2)
                lines = _wrap(clean, chars)
                for i, line in enumerate(lines):
                    prefix = "▸  " if i == 0 else "    "
                    c.drawString(ML + 8, self.y, prefix + line)
                    self.y -= 13

            self.y -= 8

    def render_skills(self, skills: list):
        """Render skills as professional rows."""
        if not skills:
            return

        self.section_header("Technical Skills")
        c = self.c

        # Clean and dedupe skills
        clean_skills = []
        seen = set()
        for skill in skills:
            s = str(skill).strip()
            if s and len(s) < 40 and s.lower() not in seen:
                clean_skills.append(s)
                seen.add(s.lower())

        if not clean_skills:
            return

        # Render as wrapped rows with bullet separators
        row_skills = []
        row_width = 0
        max_width = TW - 20

        c.setFont("Helvetica", 10)
        c.setFillColor(SLATE_700)

        for skill in clean_skills[:25]:  # Max 25 skills
            skill_width = c.stringWidth(skill, "Helvetica", 10) + 20  # +20 for separator

            if row_width + skill_width > max_width and row_skills:
                # Render current row
                self._check_space(16)
                c.drawString(ML, self.y, "  •  ".join(row_skills))
                self.y -= 14
                row_skills = []
                row_width = 0

            row_skills.append(skill)
            row_width += skill_width

        # Render remaining skills
        if row_skills:
            self._check_space(16)
            c.drawString(ML, self.y, "  •  ".join(row_skills))
            self.y -= 14

        self.y -= 6

    def render_education(self, education: list):
        """Render education entries."""
        if not education:
            return

        self.section_header("Education")
        c = self.c

        for edu in education:
            self._check_space(35)

            degree = (edu.get("degree") or "").strip()
            school = (edu.get("school") or "").strip()
            year = (edu.get("year") or "").strip()

            if not degree:
                continue

            # Degree (bold)
            c.setFont("Helvetica-Bold", 10)
            c.setFillColor(SLATE_900)
            c.drawString(ML, self.y, degree)

            # Year (right-aligned)
            if year:
                c.setFont("Helvetica", 9)
                c.setFillColor(SLATE_500)
                c.drawRightString(W - MR, self.y, year)

            self.y -= 13

            # School
            if school:
                c.setFont("Helvetica", 10)
                c.setFillColor(SLATE_700)
                c.drawString(ML, self.y, school)
                self.y -= 13

            self.y -= 4

    def render_certifications(self, certifications: list):
        """Render certifications as a bulleted list."""
        if not certifications:
            return

        self.section_header("Certifications")
        c = self.c

        for cert in certifications[:8]:  # Max 8 certifications
            clean = _clean_bullet(str(cert))
            if not clean or len(clean) < 5:
                continue

            self._check_space(16)
            c.setFont("Helvetica", 10)
            c.setFillColor(SLATE_700)
            c.drawString(ML + 8, self.y, f"▸  {clean}")
            self.y -= 13

        self.y -= 4

    def render_projects(self, projects: list):
        """Render projects section if available."""
        if not projects:
            return

        self.section_header("Key Projects")
        c = self.c

        for project in projects[:5]:  # Max 5 projects
            self._check_space(40)

            name = (project.get("name") or project.get("title") or "").strip()
            description = (project.get("description") or "").strip()
            tech = project.get("technologies") or project.get("tech") or []

            if not name:
                continue

            # Project name
            c.setFont("Helvetica-Bold", 10)
            c.setFillColor(SLATE_900)
            c.drawString(ML, self.y, name)
            self.y -= 13

            # Description
            if description:
                c.setFont("Helvetica", 10)
                c.setFillColor(SLATE_700)
                chars = int((TW - 10) / 5.2)
                for line in _wrap(description, chars)[:3]:  # Max 3 lines
                    self._check_space(14)
                    c.drawString(ML + 8, self.y, line)
                    self.y -= 13

            # Technologies
            if tech:
                c.setFont("Helvetica", 9)
                c.setFillColor(SLATE_500)
                tech_str = "Tech: " + ", ".join(str(t) for t in tech[:8])
                c.drawString(ML + 8, self.y, tech_str)
                self.y -= 13

            self.y -= 4

    def save(self):
        """Finalize and save the PDF."""
        self._page_footer()
        self.c.save()


# ─── Main Entry Point ─────────────────────────────────────────────────────────

def generate_optimized_resume(
    filename: str,
    score: float,
    improvements: list,
    resume_text: str = "",
    task_id: str = "",
    structured: dict = None,
) -> BytesIO:
    """
    Generates a premium, recruiter-grade resume PDF.

    Features:
    ✅ Professional navy header with ATS score badge
    ✅ Clean typography hierarchy
    ✅ Elegant section dividers with accent bars
    ✅ Properly formatted job entries
    ✅ Skills displayed cleanly
    ✅ ATS-compliant (standard fonts, single column)
    ✅ Page numbers

    Args:
        filename: Original filename (for reference)
        score: ATS match score (0-100) - displayed as badge
        improvements: List of improvements made (for reference)
        resume_text: Raw resume text (fallback)
        task_id: Unique task identifier
        structured: Dict with resume data (name, contact, summary, experience, skills, education, certifications)

    Returns:
        BytesIO buffer containing the PDF
    """
    buf = BytesIO()
    s = structured or {}

    # Extract data with fallbacks
    name = (s.get("name") or _extract_name(resume_text) or "Candidate").strip()
    contact = (s.get("contact") or "").strip()
    summary = (s.get("summary") or "").strip()
    experience = s.get("experience") or []
    skills = s.get("skills") or []
    education = s.get("education") or []
    certifications = s.get("certifications") or []
    projects = s.get("projects") or []

    # Create premium resume
    pdf = PremiumResume(buf, score=score)

    # Render sections
    pdf.render_header(name, contact)
    pdf.render_summary(summary)
    pdf.render_experience(experience)
    pdf.render_skills(skills)
    pdf.render_education(education)
    pdf.render_certifications(certifications)
    pdf.render_projects(projects)

    pdf.save()
    buf.seek(0)
    return buf


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _extract_name(text: str) -> str:
    """Extract name from first line of resume text."""
    for line in (text or "").split("\n"):
        line = line.strip()
        if line and len(line) < 50 and not any(c in line for c in ["@", "http", "+", "|"]):
            return line
    return "Candidate"
