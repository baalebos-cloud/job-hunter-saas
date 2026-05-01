import io
import pdfplumber
from docx import Document


async def parse_resume_to_markdown(file_bytes: bytes, filename: str = "resume.pdf") -> str:
    """
    Extracts text from PDF or DOCX and returns it as a plain string.
    Uses pdfplumber and python-docx (both already in requirements.txt).
    """
    ext = filename.rsplit(".", 1)[-1].lower()
    text = ""
    try:
        if ext == "pdf":
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    text += (page.extract_text() or "") + "\n"
        elif ext in ("docx", "doc"):
            doc = Document(io.BytesIO(file_bytes))
            for para in doc.paragraphs:
                text += para.text + "\n"
    except Exception as e:
        print(f"Parsing Error: {e}")
    return text.strip()
