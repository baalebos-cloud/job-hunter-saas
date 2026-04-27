import io
from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter

# Initialize the converter (This can be heavy, so we do it once)
converter = DocumentConverter()

async def parse_resume_to_markdown(file_bytes: bytes) -> str:
    """
    Takes raw bytes from a FastAPI upload, converts to Markdown.
    No files are saved to the EBS volume.
    """
    try:
        # 1. Wrap bytes in a file-like object
        file_stream = io.BytesIO(file_bytes)
        
        # 2. Convert using Docling (handles PDF, Docx, etc.)
        # We specify InputFormat.PDF but Docling is smart enough to auto-detect
        result = converter.convert(file_stream)
        
        # 3. Export to Markdown (LLMs love Markdown structure)
        markdown_output = result.document.export_to_markdown()
        
        return markdown_output
    except Exception as e:
        print(f"Parsing Error: {str(e)}")
        return ""
