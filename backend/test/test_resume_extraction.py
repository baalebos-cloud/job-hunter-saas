"""Reading uploaded resumes: two-column PDFs, Word headers/footers, multilingual OCR."""
import io
import time

import pdfplumber
from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from backend.app.utils import ocr
from backend.app.utils.ats_engine import extract_text
from backend.app.utils.text_extraction import find_gutter

SIDEBAR = ['SKILLS', 'Terraform', 'Kubernetes', 'Ansible', 'LANGUAGES', 'English', 'Yoruba', 'CONTACT', 'Lagos, Nigeria']
MAIN = ['EXPERIENCE', 'DevOps Engineer, Litware 2022 - Present', 'Migrated 40 services to Kubernetes on AWS EKS.',
        'Built CI/CD pipelines that cut failed deployments by 30%.', 'Cloud Engineer, Adatum 2019 - 2021',
        'Set up Prometheus alerting for 120 hosts.', 'EDUCATION', 'B.Sc. Computer Science, University of Lagos']


def two_column_pdf() -> bytes:
    out = io.BytesIO()
    c = canvas.Canvas(out, pagesize=A4)
    width, height = A4
    c.setFont('Helvetica-Bold', 18)
    c.drawCentredString(width / 2, height - 50, 'JORDAN LEE - PLATFORM ENGINEER')
    c.setFont('Helvetica', 10)
    for i, text in enumerate(SIDEBAR):
        c.drawString(40, height - 100 - i * 16, text)
    for i, text in enumerate(MAIN):
        c.drawString(200, height - 100 - i * 16, text)
    c.save()
    return out.getvalue()


def test_two_column_pdf_is_read_column_by_column():
    text = extract_text(two_column_pdf(), 'cv.pdf')
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    assert lines[0] == 'JORDAN LEE - PLATFORM ENGINEER'
    # Each column comes out whole and in order: no sidebar word inside a job line.
    assert lines[1:1 + len(SIDEBAR)] == SIDEBAR
    assert lines[1 + len(SIDEBAR):] == MAIN


def test_old_reading_interleaved_the_columns():
    # What the previous extractor produced for the same file (the bug being fixed).
    with pdfplumber.open(io.BytesIO(two_column_pdf())) as pdf:
        old = pdf.pages[0].extract_text(x_tolerance=1)
    assert 'SKILLS EXPERIENCE' in old


def test_one_column_resume_reads_exactly_as_before():
    from backend.app.utils.pdf_generator import export_resume
    pdf = export_resume({
        'name': 'Jordan Lee', 'title': 'Platform Engineer', 'contact': 'jordan@example.org | Lagos, Nigeria',
        'summary': 'Platform engineer running Kubernetes on AWS for six product teams.',
        'skills': {'Cloud': ['AWS', 'GCP'], 'IaC': ['Terraform', 'Ansible']},
        'experience': [{'role': 'DevOps Engineer', 'company': 'Litware', 'location': 'Lagos', 'dates': 'Jan 2022 - Present',
                        'bullets': ['Migrated 40 services to Kubernetes on AWS EKS.', 'Cut failed deployments by 30%.']}],
        'education': [{'degree': 'B.Sc. Computer Science', 'institution': 'University of Lagos', 'year': '2018'}],
    }, 'NG').pdf
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        old = '\n'.join(page.extract_text(x_tolerance=1) or '' for page in doc.pages).strip()
        assert all(find_gutter(p.extract_words(x_tolerance=1), float(p.width)) is None for p in doc.pages)
    assert extract_text(pdf, 'resume.pdf') == old


def test_docx_headers_and_footers_are_read():
    doc = Document()
    section = doc.sections[0]
    section.header.paragraphs[0].text = 'Ada Okafor | ada.okafor@example.org'
    section.footer.paragraphs[0].text = '+234 801 555 0101 | linkedin.com/in/adaokafor'
    section.different_first_page_header_footer = True
    section.first_page_header.paragraphs[0].text = 'Ada Okafor | ada.okafor@example.org'   # same text: kept once
    doc.add_paragraph('Professional Summary')
    doc.add_paragraph('Data analyst with five years in fintech.')
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = 'Skills'
    table.rows[0].cells[1].text = 'SQL, Python'
    out = io.BytesIO(); doc.save(out)
    text = extract_text(out.getvalue(), 'cv.docx')
    lines = [line for line in text.splitlines() if line.strip()]
    assert lines[0] == 'Ada Okafor | ada.okafor@example.org'
    assert text.count('ada.okafor@example.org') == 1
    assert lines[-1] == '+234 801 555 0101 | linkedin.com/in/adaokafor'
    assert 'Data analyst with five years in fintech.' in text and 'Skills SQL, Python' in text


def test_docx_without_headers_reads_as_before():
    doc = Document()
    doc.add_paragraph('Jordan Lee')
    doc.add_paragraph('DevOps Engineer')
    out = io.BytesIO(); doc.save(out)
    assert extract_text(out.getvalue(), 'cv.docx') == 'Jordan Lee\nDevOps Engineer'


def test_ocr_languages_use_only_installed_packs(monkeypatch):
    monkeypatch.setattr(ocr, 'OCR_LANGUAGES', 'eng+fra+deu+spa+por+ita')
    monkeypatch.setattr(ocr, 'OCR_FALLBACK_LANGUAGES', 'ara,hin')
    assert ocr.language_passes({'eng', 'fra', 'spa', 'ara', 'osd'}) == ['eng+fra+spa', 'ara+eng']
    assert ocr.language_passes({'eng'}) == ['eng']
    assert ocr.language_passes(set()) == ['eng']        # nothing listed: plain English, as before


class FakeTesseract:
    def __init__(self, results):
        self.results, self.calls = results, []

    def get_languages(self, config=''):
        return ['eng', 'fra', 'deu', 'spa', 'por', 'ita', 'ara', 'hin']

    def image_to_string(self, image, lang='eng', timeout=0):
        self.calls.append(lang)
        return self.results.get(lang, '')


def test_ocr_tries_other_scripts_only_when_latin_finds_little(monkeypatch):
    monkeypatch.setattr(ocr, '_installed', None)
    latin = FakeTesseract({'eng+fra+deu+spa+por+ita': 'Ingénieure DevOps, Paris. Kubernetes, Terraform, AWS depuis 2019.'})
    assert ocr._read_image(latin, None, time.monotonic() + 10).startswith('Ingénieure')
    assert latin.calls == ['eng+fra+deu+spa+por+ita']

    monkeypatch.setattr(ocr, '_installed', None)
    arabic_text = 'مهندس سحابة لديه خبرة في كوبرنيتس وتيرافورم وخدمات أمازون السحابية منذ عام ألفين وتسعة عشر'
    arabic = FakeTesseract({'eng+fra+deu+spa+por+ita': '|| ~', 'ara+eng': arabic_text})
    assert ocr._read_image(arabic, None, time.monotonic() + 10) == arabic_text
    assert arabic.calls == ['eng+fra+deu+spa+por+ita', 'ara+eng']
