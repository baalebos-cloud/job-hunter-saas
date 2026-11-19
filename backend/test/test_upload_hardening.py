"""Upload validation (magic bytes, page cap, zip bombs) and the OCR fallback."""
import importlib
import io
import shutil
import zipfile

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from backend.app.utils import ocr
from backend.app.utils.upload_validation import UploadRejected, validate_upload


def docx_bytes(paragraph='Ada Obi resume'):
    from docx import Document
    buffer = io.BytesIO()
    doc = Document(); doc.add_paragraph(paragraph); doc.save(buffer)
    return buffer.getvalue()


def zip_with(extra: dict, base=True):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        if base:
            archive.writestr('[Content_Types].xml', '<Types/>')
            archive.writestr('word/document.xml', '<w:document/>')
        for name, data in extra.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def pdf_with_pages(count, text='Resume text for page'):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    for i in range(count):
        c.drawString(72, 750, f'{text} {i}'); c.showPage()
    c.save()
    return buffer.getvalue()


def test_valid_documents_pass():
    assert validate_upload('cv.docx', docx_bytes()) == 'docx'
    assert validate_upload('cv.pdf', pdf_with_pages(2)) == 'pdf'


@pytest.mark.parametrize('name,content,message', [
    ('cv.pdf', b'PK\x03\x04 not a pdf', 'not a PDF'),
    ('cv.docx', b'%PDF-1.4 not a docx', 'not a Word document'),
    ('cv.doc', b'\xd0\xcf\x11\xe0', 'Legacy .doc'),
    ('cv.exe', b'MZ', 'Use PDF or DOCX'),
    ('cv.pdf', b'', 'empty'),
])
def test_magic_bytes_and_extensions(name, content, message):
    with pytest.raises(UploadRejected, match=message):
        validate_upload(name, content)


def test_zip_bomb_by_total_size_is_rejected_without_decompressing():
    bomb = zip_with({'word/media/zeros.bin': b'\0' * (51 * 1024 * 1024)})
    assert len(bomb) < 1024 * 1024
    with pytest.raises(UploadRejected, match='50 MB'):
        validate_upload('cv.docx', bomb)


def test_zip_bomb_by_ratio_is_rejected():
    with pytest.raises(UploadRejected, match='compression ratio'):
        validate_upload('cv.docx', zip_with({'word/media/zeros.bin': b'\0' * (5 * 1024 * 1024)}))


def test_docx_structure_macros_and_entry_count():
    with pytest.raises(UploadRejected, match='not a Word document'):
        validate_upload('cv.docx', zip_with({'other.xml': '<x/>'}, base=False))
    with pytest.raises(UploadRejected, match='macros'):
        validate_upload('cv.docx', zip_with({'word/vbaProject.bin': b'macro'}))
    with pytest.raises(UploadRejected, match='too many parts'):
        validate_upload('cv.docx', zip_with({f'word/p{i}.xml': 'x' for i in range(1001)}))


def test_pdf_page_cap_and_encryption():
    with pytest.raises(UploadRejected, match='15 pages'):
        validate_upload('cv.pdf', pdf_with_pages(16))
    from pypdf import PdfReader, PdfWriter
    writer = PdfWriter(); writer.append(PdfReader(io.BytesIO(pdf_with_pages(1))))
    writer.encrypt('secret')
    buffer = io.BytesIO(); writer.write(buffer)
    with pytest.raises(UploadRejected, match='password-protected'):
        validate_upload('cv.pdf', buffer.getvalue())


def image_only_pdf():
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new('L', (1700, 600), 255)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype('backend/app/assets/fonts/DejaVuSans.ttf', 48)
    for i, line in enumerate(['Ada Obi Platform Engineer', 'Python Terraform Kubernetes AWS', 'Built deployment pipelines']):
        draw.text((40, 40 + i * 120), line, fill=0, font=font)
    buffer = io.BytesIO()
    image.save(buffer, format='PDF', resolution=200)
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def fresh_breaker(monkeypatch):
    monkeypatch.setattr(ocr, 'breaker', ocr.CircuitBreaker(threshold=3, cooldown=60))


@pytest.mark.skipif(not (shutil.which('tesseract') and shutil.which('pdftoppm')), reason='tesseract/poppler not installed')
def test_scanned_pdf_falls_back_to_ocr():
    from backend.app.utils.ats_engine import extract_text, extract_text_with_ocr
    pdf = image_only_pdf()
    assert extract_text(pdf, 'cv.pdf') == ''
    recovered = extract_text_with_ocr(pdf, 'cv.pdf')
    assert 'Platform Engineer' in recovered and 'Kubernetes' in recovered


def test_cid_text_triggers_ocr(monkeypatch):
    from backend.app.utils import ats_engine
    monkeypatch.setattr(ats_engine, 'extract_text', lambda *a: 'GitHubAc(cid:415)ons and Terraform (cid:12)(cid:13)')
    monkeypatch.setattr(ocr, 'ocr_pdf', lambda content, **kw: 'GitHub Actions and Terraform experience across five teams.')
    assert ats_engine.extract_text_with_ocr(b'%PDF-', 'cv.pdf').startswith('GitHub Actions')
    assert ocr.needs_ocr('short') and ocr.needs_ocr('x' * 50 + '(cid:3)') and not ocr.needs_ocr('x' * 50)


def test_ocr_timeout_and_circuit_breaker(monkeypatch):
    pytest.importorskip('pytesseract')
    if not shutil.which('pdftoppm'):
        pytest.skip('poppler not installed')
    import pytesseract
    calls = []
    def timeout(*args, **kwargs):
        calls.append(kwargs.get('timeout'))
        raise RuntimeError('Tesseract process timeout')
    monkeypatch.setattr(pytesseract, 'image_to_string', timeout)
    pdf = pdf_with_pages(1)
    for _ in range(3):
        with pytest.raises(ocr.OcrUnavailable, match='in time'):
            ocr.ocr_pdf(pdf, timeout=5)
    assert all(0 < t <= 5 for t in calls)
    with pytest.raises(ocr.OcrUnavailable, match='temporarily unavailable'):
        ocr.ocr_pdf(pdf)
    assert len(calls) == 3  # breaker open: engine not called again


def test_ocr_page_cap_does_not_trip_breaker():
    for _ in range(5):
        with pytest.raises(ocr.OcrUnavailable, match='limited to 2 pages'):
            ocr.ocr_pdf(pdf_with_pages(3), max_pages=2)
    assert not ocr.breaker.is_open


def test_dpi_is_capped_for_huge_pages():
    assert ocr._safe_dpi(595, 842, 600) == ocr.OCR_MAX_DPI or ocr._safe_dpi(595, 842, 600) <= 300
    assert ocr._safe_dpi(72 * 200, 72 * 200, 300) <= 50


def test_legacy_parsers_are_removed():
    for module in ('backend.app.parser', 'backend.app.services.resume_service'):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(module)
