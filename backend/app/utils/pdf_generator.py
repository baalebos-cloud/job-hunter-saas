from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from io import BytesIO
import textwrap

W, H   = LETTER
ML     = 54
MR     = 54
TW     = W - ML - MR
BLACK  = colors.black
DGRAY  = colors.HexColor("#333333")
MGRAY  = colors.HexColor("#555555")
PRIMARY = colors.HexColor("#1e40af")  # Professional Blue
ACCENT = colors.HexColor("#0369a1")   # Steel Blue


def _wrap(text: str, chars: int) -> list:
    return textwrap.wrap(str(text).strip(), width=max(chars, 20)) or [""]


def _render_contact(c, rc, contact: str):
    """
    FIXED: Replaces the old `contact[:130]` hard truncation.
    Renders contact line centered. If too wide for one line, splits
    on ' | ' and wraps to two lines — nothing gets cut off.
    """
    if not contact or not contact.strip():
        return
    c.setFont("Helvetica", 9.5)
    c.setFillColor(DGRAY)
    max_width = W - ML - MR  # ~504 pts

    string_width = c.stringWidth(contact, "Helvetica", 9.5)

    if string_width <= max_width:
        c.drawCentredString(W / 2, rc.y, contact)
        rc.y -= 14
    else:
        # Split on separator and render two lines
        parts = contact.split("  |  ")
        mid   = max(1, len(parts) // 2)
        line1 = "  |  ".join(parts[:mid])
        line2 = "  |  ".join(parts[mid:])
        c.drawCentredString(W / 2, rc.y, line1)
        rc.y -= 12
        if line2.strip():
            c.drawCentredString(W / 2, rc.y, line2)
            rc.y -= 12


class RC:
    """Resume Canvas — thin wrapper around ReportLab canvas."""

    def __init__(self, buf):
        self.c   = canvas.Canvas(buf, pagesize=LETTER)
        self.y   = H - ML
        self._pg = 1

    def _footer(self):
        self.c.setFont("Helvetica", 7)
        self.c.setFillColor(MGRAY)
        self.c.drawCentredString(W / 2, 18, f"Page {self._pg}")

    def need(self, space: int = 40):
        if self.y < space + 55:
            self._footer()
            self.c.showPage()
            self._pg += 1
            self.y = H - ML

    def heading(self, title: str):
        self.y -= 10
        self.need(55)
        self.c.setFont("Helvetica-Bold", 10.5)
        self.c.setFillColor(PRIMARY)
        self.c.drawString(ML, self.y, title.upper())
        self.y -= 4
        self.c.setStrokeColor(PRIMARY)
        self.c.setLineWidth(1.5)
        self.c.line(ML, self.y, W - MR, self.y)
        self.c.setLineWidth(0.4)
        self.y -= 12

    def line(self, txt: str, bold=False, size=10, indent=0, color=None):
        if not txt or not txt.strip():
            return
        self.c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        self.c.setFillColor(color or BLACK)
        chars = int((TW - indent) / (size * 0.56))
        for ln in _wrap(txt, chars):
            self.need()
            self.c.drawString(ML + indent, self.y, ln)
            self.y -= size + 3

    def bullet(self, txt: str):
        if not txt or not txt.strip():
            return
        clean = txt.lstrip("•-*– ").strip()
        chars = int((TW - 18) / 5.8)
        lines = _wrap(clean, chars)
        for i, ln in enumerate(lines):
            self.need()
            self.c.setFont("Helvetica", 10)
            self.c.setFillColor(BLACK)
            prefix = "• " if i == 0 else "  "
            self.c.drawString(ML + 6, self.y, prefix + ln)
            self.y -= 13

    def job_header(self, title: str, company: str, dates: str, location: str = ""):
        self.need(50)
        self.c.setFont("Helvetica-Bold", 11)
        self.c.setFillColor(ACCENT)
        self.c.drawString(ML, self.y, title)
        if dates:
            self.c.setFont("Helvetica", 9.5)
            self.c.setFillColor(MGRAY)
            self.c.drawRightString(W - MR, self.y, dates)
        self.y -= 13
        if company or location:
            self.c.setFont("Helvetica", 10)
            self.c.setFillColor(DGRAY)
            parts = [p for p in [company, location] if p]
            self.c.drawString(ML, self.y, "  •  ".join(parts))
            self.y -= 13

    def skills_row(self, skills: list):
        if not skills:
            return
        clean = [str(s).strip() for s in skills if s and str(s).strip()]
        for i in range(0, len(clean), 4):
            chunk = clean[i:i + 4]
            self.c.setFont("Helvetica", 10)
            self.c.setFillColor(BLACK)
            self.need(16)
            self.c.drawString(ML, self.y, "  •  ".join(chunk))
            self.y -= 13

    def save(self):
        self._footer()
        self.c.save()


# ── Main entry point ────────────────────────────────────────────────────────

def generate_optimized_resume(
    filename: str,
    score: float,
    improvements: list,
    resume_text: str = "",
    task_id: str = "",
    structured: dict = None,
) -> BytesIO:
    """
    Generates a professional, visually-appealing resume PDF optimized for recruiters.

    Features:
    ✅ Professional color scheme (blue accents)
    ✅ Clear visual hierarchy
    ✅ ATS-compliant formatting
    ✅ Single column layout
    ✅ Standard fonts (Helvetica)
    ✅ Consistent spacing and margins
    ✅ Polished section dividers
    ✅ Auto-wrapping contact info
    ✅ Page numbers
    
    Pass the `structured` dict from optimizer.build_optimized_resume()
    to get a fully populated resume. Without it the PDF will be nearly blank.
    """
    buf = BytesIO()
    s   = structured or {}

    name           = (s.get("name") or _first_line(resume_text) or "Candidate").strip()
    contact        = (s.get("contact") or _second_line(resume_text) or "").strip()
    summary        = (s.get("summary") or "").strip()
    experience     = s.get("experience") or []
    skills         = s.get("skills") or []
    education      = s.get("education") or []
    certifications = s.get("certifications") or []

    rc = RC(buf)
    c  = rc.c

    # ── PROFESSIONAL HEADER ──────────────────────────────────────────────────
    c.setFont("Helvetica-Bold", 22)
    c.setFillColor(PRIMARY)
    c.drawCentredString(W / 2, rc.y, name.upper())
    rc.y -= 24

    # Contact info with wrapping
    if contact:
        _render_contact(c, rc, contact)
    else:
        rc.y -= 4

    # Professional divider
    c.setStrokeColor(PRIMARY)
    c.setLineWidth(2)
    c.line(ML, rc.y, W - MR, rc.y)
    c.setLineWidth(0.4)
    rc.y -= 16

    # ── PROFESSIONAL SUMMARY ──────────────────────────────────────────────────
    if summary:
        rc.heading("Professional Summary")
        chars = int(TW / 5.6)
        for ln in _wrap(summary, chars):
            rc.need()
            c.setFont("Helvetica", 10)
            c.setFillColor(BLACK)
            c.drawString(ML, rc.y, ln)
            rc.y -= 13
        rc.y -= 4

    # ── WORK EXPERIENCE ───────────────────────────────────────────────────────
    if experience:
        rc.heading("Work Experience")
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
        rc.heading("Technical Skills")
        rc.skills_row(skills)
        rc.y -= 4

    # ── EDUCATION ────────────────────────────────────────────────────────────
    if education:
        rc.heading("Education")
        for edu in education:
            degree = (edu.get("degree") or "").strip()
            school = (edu.get("school") or "").strip()
            year   = (edu.get("year") or "").strip()
            rc.need(38)
            c.setFont("Helvetica-Bold", 10.5)
            c.setFillColor(ACCENT)
            c.drawString(ML, rc.y, degree)
            if year:
                c.setFont("Helvetica", 9.5)
                c.setFillColor(MGRAY)
                c.drawRightString(W - MR, rc.y, year)
            rc.y -= 13
            if school:
                c.setFont("Helvetica", 10)
                c.setFillColor(DGRAY)
                c.drawString(ML, rc.y, school)
                rc.y -= 13

    # ── CERTIFICATIONS ───────────────────────────────────────────────────────
    if certifications:
        rc.heading("Certifications")
        for cert in certifications:
            if cert and cert.strip():
                rc.bullet(cert.strip())

    rc.save()
    buf.seek(0)
    return buf


# ── Helpers ───────────────────────────────────────────────────────────────────

def _first_line(text: str) -> str:
    for ln in (text or "").split("\n"):
        if ln.strip():
            return ln.strip()
    return "Candidate"


def _second_line(text: str) -> str:
    found = 0
    for ln in (text or "").split("\n"):
        if ln.strip():
            found += 1
            if found == 2:
                return ln.strip()
    return ""
