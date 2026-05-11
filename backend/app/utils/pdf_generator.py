from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from io import BytesIO
import textwrap

W, H = LETTER
ML = 60       # left margin
MR = 60       # right margin
TW = W - ML - MR

# ATS-safe: black only, no colors, standard Helvetica font
C_BLACK  = colors.black
C_GRAY   = colors.HexColor("#444444")
C_LGRAY  = colors.HexColor("#666666")


def _wrap(text: str, max_chars: int) -> list:
    return textwrap.wrap(str(text).strip(), width=max(max_chars, 20)) or [""]


class ResumeCanvas:
    def __init__(self, buf):
        self.p = canvas.Canvas(buf, pagesize=LETTER)
        self.y = H - ML
        self._page = 1

    def _draw_footer(self):
        self.p.setFont("Helvetica", 7)
        self.p.setFillColor(C_LGRAY)
        self.p.drawCentredString(W / 2, 20, f"Page {self._page}")

    def check_page(self, needed=40):
        if self.y < needed + 60:
            self._draw_footer()
            self.p.showPage()
            self._page += 1
            self.y = H - ML

    def section_heading(self, title: str):
        self.y -= 10
        self.check_page(60)
        # Full-width underline heading — ATS standard
        self.p.setFont("Helvetica-Bold", 10.5)
        self.p.setFillColor(C_BLACK)
        self.p.drawString(ML, self.y, title.upper())
        self.y -= 3
        self.p.setStrokeColor(C_BLACK)
        self.p.setLineWidth(0.8)
        self.p.line(ML, self.y, W - MR, self.y)
        self.p.setLineWidth(0.5)
        self.y -= 12

    def text_line(self, txt: str, bold=False, size=10, indent=0, color=None):
        if not txt or not txt.strip():
            return
        self.p.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        self.p.setFillColor(color or C_BLACK)
        for line in _wrap(txt, int((TW - indent) / 5.5)):
            self.check_page()
            self.p.drawString(ML + indent, self.y, line)
            self.y -= 13

    def bullet(self, txt: str):
        if not txt or not txt.strip():
            return
        clean = txt.lstrip("•-*– ").strip()
        lines = _wrap(clean, int((TW - 16) / 5.5))
        for i, line in enumerate(lines):
            self.check_page()
            if i == 0:
                # Plain hyphen bullet — ATS safe
                self.p.setFont("Helvetica", 10)
                self.p.setFillColor(C_BLACK)
                self.p.drawString(ML + 4, self.y, f"- {line}")
            else:
                self.p.drawString(ML + 14, self.y, line)
            self.y -= 13

    def job_header(self, title: str, company: str, dates: str, location: str = ""):
        self.check_page(55)
        # Title left, dates right — standard ATS format
        self.p.setFont("Helvetica-Bold", 10.5)
        self.p.setFillColor(C_BLACK)
        self.p.drawString(ML, self.y, title)
        if dates:
            self.p.setFont("Helvetica", 9.5)
            self.p.setFillColor(C_GRAY)
            self.p.drawRightString(W - MR, self.y, dates)
        self.y -= 13
        # Company + location on next line
        if company or location:
            self.p.setFont("Helvetica", 10)
            self.p.setFillColor(C_GRAY)
            line = company
            if location:
                line = f"{company}  |  {location}" if company else location
            self.p.drawString(ML, self.y, line)
            self.y -= 13

    def skills_line(self, skills: list):
        """Render skills as plain comma-separated text — most ATS-friendly format."""
        if not skills:
            return
        clean = [str(s).strip() for s in skills if s and str(s).strip()]
        # Group into rows of 5
        for i in range(0, len(clean), 5):
            chunk = clean[i:i + 5]
            line = "  |  ".join(chunk)
            self.p.setFont("Helvetica", 10)
            self.p.setFillColor(C_BLACK)
            self.check_page(20)
            self.p.drawString(ML, self.y, line)
            self.y -= 13

    def save(self):
        self._draw_footer()
        self.p.save()


def generate_optimized_resume(
    filename: str,
    score: float,
    improvements: list,
    resume_text: str = "",
    task_id: str = "",
    structured: dict = None
) -> BytesIO:
    """
    Generates a clean, ATS-optimised single-column resume PDF.
    - Black and white only (no colors — ATS scanners strip colors)
    - Standard Helvetica font (universally parseable)
    - No tables, no columns, no graphics
    - Plain hyphen bullets (ATS-safe)
    - Full-width section dividers
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

    # ── NAME ─────────────────────────────────────────────────────────────────
    p.setFont("Helvetica-Bold", 18)
    p.setFillColor(C_BLACK)
    p.drawCentredString(W / 2, rc.y, name.upper())
    rc.y -= 18

    # ── CONTACT LINE ─────────────────────────────────────────────────────────
    if contact:
        p.setFont("Helvetica", 9.5)
        p.setFillColor(C_GRAY)
        p.drawCentredString(W / 2, rc.y, contact[:120])
        rc.y -= 8

    # Thin divider under header
    p.setStrokeColor(C_BLACK)
    p.setLineWidth(0.8)
    p.line(ML, rc.y, W - MR, rc.y)
    p.setLineWidth(0.5)
    rc.y -= 14

    # ── PROFESSIONAL SUMMARY ──────────────────────────────────────────────────
    if summary:
        rc.section_heading("Professional Summary")
        rc.text_line(summary, size=10)
        rc.y -= 4

    # ── WORK EXPERIENCE ───────────────────────────────────────────────────────
    if experience:
        rc.section_heading("Work Experience")
        for job in experience:
            rc.job_header(
                (job.get("title") or "").strip(),
                (job.get("company") or "").strip(),
                (job.get("dates") or "").strip(),
                (job.get("location") or "").strip(),
            )
            for b in (job.get("bullets") or []):
                if b and b.strip():
                    rc.bullet(b.strip())
            rc.y -= 6

    # ── TECHNICAL SKILLS ─────────────────────────────────────────────────────
    if skills:
        rc.section_heading("Technical Skills")
        rc.skills_line(skills)
        rc.y -= 4

    # ── EDUCATION ────────────────────────────────────────────────────────────
    if education:
        rc.section_heading("Education")
        for edu in education:
            degree = (edu.get("degree") or "").strip()
            school = (edu.get("school") or "").strip()
            year   = (edu.get("year") or "").strip()
            rc.check_page(40)
            p.setFont("Helvetica-Bold", 10.5)
            p.setFillColor(C_BLACK)
            p.drawString(ML, rc.y, degree)
            if year:
                p.setFont("Helvetica", 9.5)
                p.setFillColor(C_GRAY)
                p.drawRightString(W - MR, rc.y, year)
            rc.y -= 13
            if school:
                p.setFont("Helvetica", 10)
                p.setFillColor(C_GRAY)
                p.drawString(ML, rc.y, school)
                rc.y -= 13

    # ── CERTIFICATIONS ────────────────────────────────────────────────────────
    if certifications:
        rc.section_heading("Certifications")
        for cert in certifications:
            if cert and cert.strip():
                rc.bullet(cert.strip())

    rc.save()
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
