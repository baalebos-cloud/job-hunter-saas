import io
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from docling.document_converter import DocumentConverter

# --- IMPORT YOUR EXISTING LOGIC ---
from backend.app.database import Base, engine, get_db
from backend.app.routes import jobs, resume, auth, application, dashboard, outreach
from backend.app.models.resume import Resume
from backend.app.utils.pdf_generator import generate_optimized_resume
from backend.app.celery_app import celery_app

# --- INITIALIZE APP & AI ---
app = FastAPI(
    title="Baalebos Cloud AI",
    description="Global Talent Engine: AI Resume Analysis & Job Tracking",
    version="1.5.0"
)

# Initialize Docling once (at the top level for efficiency)
converter = DocumentConverter()

# --- PRODUCTION CORS ---
origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://baalebo.xyz",
    "https://baalebo.xyz",
    "http://www.baalebo.xyz",
    "https://www.baalebo.xyz",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- INCLUDE YOUR EXISTING ROUTES ---
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["Jobs"])
app.include_router(resume.router, prefix="/api/v1/resume", tags=["Resumes"])
app.include_router(application.router, prefix="/api/v1/applications", tags=["Applications"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
# app.include_router(outreach.router, prefix="/api/v1/outreach", tags=["Outreach"])

# --- NEW AI PARSER ENDPOINT ---
@app.post("/api/v1/ai/parse-test", tags=["AI Engine"])
async def test_ai_parsing(file: UploadFile = File(...)):
    """
    Directly tests the Docling parser without saving to DB.
    """
    if not file.filename.lower().endswith(('.pdf', '.docx')):
        raise HTTPException(status_code=400, detail="Unsupported file format.")

    try:
        content = await file.read()
        file_stream = io.BytesIO(content)
        result = converter.convert(file_stream)
        markdown_text = result.document.export_to_markdown()
        
        return {
            "filename": file.filename,
            "parsed_content": markdown_text[:1000], # Preview
            "length": len(markdown_text)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Parsing Error: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.5.0", "domain": "baalebo.xyz"}
