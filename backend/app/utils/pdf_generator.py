import textwrap
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from io import BytesIO

W, H = LETTER
ML = 55   # left margin
MR = 55   # right margin
TW = W - ML - MR

# Clean professional color palette
C_NAME    = colors.HexColor("#0f172a")   # near-black for name
C_HEADING = colors.HexColor("#1e3a5f")   # dark navy for section headings
C_ACCENT  = colors.HexColor("#2563eb")   # blue accent line
C_BODY    = colors.HexColor("#1e293b")   # dark body text
C_SUB     = colors.HexColor("#475569")   # secondary text (company, dates)
C_WHITE   = colors.white


def _wrap(text: str, max_chars: int) -> list:
    return textwrap.wrap(str(text).strip(), width=max(max_chars, 20)) or [""]


class ResumeCanvas:
    def __init__(self, buf):
        self.p = canvas.Canvas(buf, pagesize=LETTER)
        self.y = H - ML

    def check_page(self, needed=40):
        if self.y < needed + 36:
            self.p.showPage()
            self.y = H - ML

    def section_heading(self, title):
        self.y -= 12
        self.check_page(60)
        # Section title
        self.p.setFont("Helvetica-Bold", 9.5)
        self.p.setFillColor(C_HEADING)
        self.p.drawString(ML, self.y, title.upper())
        self.y -= 4
        # Accent underline
        self.p.setStrokeColor(C_ACCENT)
        self.p.setLineWidth(1.5)
        self.p.line(ML, self.y, W - MR, self.y)
        self.p.setLineWidth(0.5)
        self.y -= 12

    def text_line(self, txt, bold=False, color=None, size=9.5, indent=0):
        if not txt or not txt.strip():
            return
        if color is None:
            color = C_BODY
        font = "Helvetica-Bold" if bold else "Helvetica"
        self.p.setFont(font, size)
        self.p.setFillColor(color)
        for line in _wrap(txt, int((TW - indent) / 5.2)):
            self.check_page()
            self.p.drawString(ML + indent, self.y, line)
            self.y -= 13

    def bullet(self, txt, indent=12):
        if not txt or not txt.strip():
            return
        self.p.setFont("Helvetica", 9.5)
        self.p.setFillColor(C_BODY)
        lines = _wrap(txt.lstrip("•-* "), int((TW - indent - 8) / 5.2))
        for i, line in enumerate(lines):
            self.check_page()
            if i == 0:
                self.p.setFillColor(C_ACCENT)
                self.p.circle(ML + indent - 4, self.y + 3.5, 2, fill=1, stroke=0)
                self.p.setFillColor(C_BODY)
                self.p.drawString(ML + indent + 4, self.y, line)
            else:
                self.p.drawString(ML + indent + 4, self.y, line)
            self.y -= 13

    def job_header(self, title, company, dates, location=""):
        self.check_page(60)
        # Job title
        self.p.setFont("Helvetica-Bold", 10)
        self.p.setFillColor(C_BODY)
        self.p.drawString(ML, self.y, title)
        # Dates right-aligned
        if dates:
            self.p.setFont("Helvetica", 8.5)
            self.p.setFillColor(C_SUB)
            self.p.drawRightString(W - MR, self.y, dates)
        self.y -= 13
        # Company + location
        if company or location:
            self.p.setFont("Helvetica-Bold", 9)
            self.p.setFillColor(C_ACCENT)
            line = company
            if location:
                line += f"  ·  {location}" if company else location
            self.p.drawString(ML, self.y, line)
            self.y -= 13

    def skill_pills(self, skills):
        """Render skills as inline comma-separated text — clean and ATS-friendly."""
        if not skills:
            return
        self.check_page(30)
        # Group into rows of ~8 skills
        row_size = 8
        for i in range(0, len(skills), row_size):
            chunk = skills[i:i + row_size]
            line = "  ·  ".join(str(s).strip() for s in chunk if s)
            self.p.setFont("Helvetica", 9.5)
            self.p.setFillColor(C_BODY)
            self.check_page()
            self.p.drawString(ML, self.y, line)
            self.y -= 14

    def footer(self, page_num=1):
        self.p.setFont("Helvetica", 7.5)
        self.p.setFillColor(colors.HexColor("#cbd5e1"))
        self.p.drawCentredString(W / 2, 20, f"Page {page_num}")


def generate_optimized_resume(filename: str, score: float, improvements: list,
                               resume_text: str = "", task_id: str = "",
                               structured: dict = None) -> BytesIO:
    """
    Generates a clean, standard professional resume PDF.
    - No branding, no ATS score badge, no optimization report page
    - AI improvements are embedded directly into the resume content
    - Looks exactly like a resume a hiring manager would receive
    """
    buf = BytesIO()
    s = structured or {}

    name           = (s.get("name") or _first_line(resume_text) or "Candidate").strip()
    contact        = (s.get("contact") or _second_line(resume_text) or "").strip()
    summary        = (s.get("summary") or "").strip()
    experience     = s.get("experience") or []
    skills         = s.get("skills") or []
    education      = s.get("education") or []
    certifications = s.get("certifications") or []

    rc = ResumeCanvas(buf)
    p  = rc.p

    # ── NAME & CONTACT HEADER ─────────────────────────────────────────────────
    # Name — large, centered
    p.setFont("Helvetica-Bold", 20)
    p.setFillColor(C_NAME)
    p.drawCentredString(W / 2, rc.y, name.upper())
    rc.y -= 22

    # Contact line — centered, smaller
    if contact:
        p.setFont("Helvetica", 9)
        p.setFillColor(C_SUB)
        # Truncate if too long
        contact_display = contact[:100]
        p.drawCentredString(W / 2, rc.y, contact_display)
        rc.y -= 10

    # Thin accent line under header
    p.setStrokeColor(C_ACCENT)
    p.setLineWidth(1.5)
    p.line(ML, rc.y, W - MR, rc.y)
    p.setLineWidth(0.5)
    rc.y -= 16

    # ── PROFESSIONAL SUMMARY ──────────────────────────────────────────────────
    if summary:
        rc.section_heading("Professional Summary")
        rc.text_line(summary, size=9.5)
        rc.y -= 4

    # ── WORK EXPERIENCE ───────────────────────────────────────────────────────
    if experience:
        rc.section_heading("Work Experience")
        for job in experience:
            title   = (job.get("title") or "").strip()
            company = (job.get("company") or "").strip()
            dates   = (job.get("dates") or "").strip()
            loc     = (job.get("location") or "").strip()
            bullets = job.get("bullets") or []

            rc.job_header(title, company, dates, loc)
            for b in bullets:
                if b and b.strip():
                    rc.bullet(b.strip())
            rc.y -= 6

    # ── TECHNICAL SKILLS ─────────────────────────────────────────────────────
    if skills:
        rc.section_heading("Technical Skills")
        rc.skill_pills(skills)
        rc.y -= 4

    # ── EDUCATION ────────────────────────────────────────────────────────────
    if education:
        rc.section_heading("Education")
        for edu in education:
            degree = (edu.get("degree") or "").strip()
            school = (edu.get("school") or "").strip()
            year   = (edu.get("year") or "").strip()
            rc.check_page(40)
            p.setFont("Helvetica-Bold", 9.5)
            p.setFillColor(C_BODY)
            p.drawString(ML, rc.y, degree)
            if year:
                p.setFont("Helvetica", 8.5)
                p.setFillColor(C_SUB)
                p.drawRightString(W - MR, rc.y, year)
            rc.y -= 13
            if school:
                p.setFont("Helvetica", 9)
                p.setFillColor(C_SUB)
                p.drawString(ML, rc.y, school)
                rc.y -= 13

    # ── CERTIFICATIONS ────────────────────────────────────────────────────────
    if certifications:
        rc.section_heading("Certifications")
        for cert in certifications:
            if cert and cert.strip():
                rc.bullet(cert.strip())

    rc.footer(1)
    p.save()
    buf.seek(0)
    return buf


def _first_line(text: str) -> str:
    for line in (text or "").split("\n"):
        if line.strip():
            return line.strip()
    return "Candidate"


def _second_line(text: str) -> str:
    found = 0
    for line in (text or "").split("\n"):
        if line.strip():
            found += 1
            if found == 2:
                return line.strip()
    return ""
