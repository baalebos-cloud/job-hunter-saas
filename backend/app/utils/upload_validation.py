"""Upload validation: magic bytes, PDF page cap and DOCX zip-bomb defence.

Runs before any parser touches the file.
"""
from __future__ import annotations

import io
import zipfile

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 15
MAX_DOCX_UNCOMPRESSED = 50 * 1024 * 1024
MAX_DOCX_ENTRIES = 1000
MAX_COMPRESSION_RATIO = 100  # per entry, for entries larger than 1 MiB
RATIO_CHECK_MIN_BYTES = 1024 * 1024
MACRO_PARTS = ('word/vbaproject.bin', 'word/vbadata.xml')


class UploadRejected(ValueError):
    """The upload is not a safe, supported resume document."""


def detect_kind(filename: str, content: bytes) -> str:
    name = (filename or '').lower()
    if name.endswith('.pdf'):
        if not content.lstrip()[:5].startswith(b'%PDF-'):
            raise UploadRejected('Invalid PDF: the file content is not a PDF.')
        return 'pdf'
    if name.endswith('.docx'):
        if not content.startswith(b'PK\x03\x04'):
            raise UploadRejected('Invalid DOCX: the file content is not a Word document.')
        return 'docx'
    if name.endswith('.doc'):
        raise UploadRejected('Legacy .doc files are not supported. Save the resume as DOCX or PDF and upload it again.')
    raise UploadRejected('Use PDF or DOCX.')


def validate_pdf(content: bytes) -> int:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError
    try:
        reader = PdfReader(io.BytesIO(content), strict=False)
        if reader.is_encrypted:
            raise UploadRejected('This PDF is password-protected. Upload an unprotected copy.')
        pages = len(reader.pages)
    except UploadRejected:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError) as exc:
        raise UploadRejected('Invalid PDF: the file could not be read.') from exc
    if pages == 0:
        raise UploadRejected('Invalid PDF: the document has no pages.')
    if pages > MAX_PDF_PAGES:
        raise UploadRejected(f'Resumes longer than {MAX_PDF_PAGES} pages are not supported.')
    return pages


def validate_docx(content: bytes) -> None:
    """Check the ZIP central directory without decompressing anything."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except (zipfile.BadZipFile, ValueError) as exc:
        raise UploadRejected('Invalid DOCX: the archive is damaged.') from exc
    with archive:
        entries = archive.infolist()
        if len(entries) > MAX_DOCX_ENTRIES:
            raise UploadRejected('Invalid DOCX: too many parts.')
        names = {info.filename.lower() for info in entries}
        if '[content_types].xml' not in names or 'word/document.xml' not in names:
            raise UploadRejected('Invalid DOCX: this is not a Word document.')
        if any(part in names for part in MACRO_PARTS):
            raise UploadRejected('Documents containing macros are not accepted. Save as a plain .docx.')
        total = 0
        for info in entries:
            if info.flag_bits & 0x1:
                raise UploadRejected('Encrypted DOCX files are not supported.')
            total += info.file_size
            if total > MAX_DOCX_UNCOMPRESSED:
                raise UploadRejected('Invalid DOCX: uncompressed content exceeds 50 MB.')
            if info.file_size > RATIO_CHECK_MIN_BYTES and info.file_size > MAX_COMPRESSION_RATIO * max(info.compress_size, 1):
                raise UploadRejected('Invalid DOCX: suspicious compression ratio.')


def validate_upload(filename: str, content: bytes) -> str:
    if len(content) > MAX_UPLOAD_BYTES:
        raise UploadRejected('Maximum file size is 10MB.')
    if not content:
        raise UploadRejected('The uploaded file is empty.')
    kind = detect_kind(filename, content)
    if kind == 'pdf':
        validate_pdf(content)
    else:
        validate_docx(content)
    return kind
