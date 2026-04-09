import io
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from docling.document_converter import DocumentConverter

# --- EXISTING LOGIC ---
from backend.app.database import Base, engine, get_db
from backend.app.routes import jobs, resume, auth, application, dashboard, upload, output
from backend.app.ai_engine import get_resume_match_score # <--- YOUR NEW FILE

# --- INITIALIZE APP & AI ---
app = FastAPI(title="Baalebos Cloud AI")

# Initialize Docling once for memory efficiency
converter = DocumentConverter()

# --- PRODUCTION CORS ---
origins = [
    "http://localhost:5173",
    "https://baalebo.xyz",
    "https://www.baalebo.xyz",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://baalebo.xyz"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- INCLUDE EXISTING ROUTES ---
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["Jobs"])
app.include_router(resume.router, prefix="/api/v1/resume", tags=["Resume"])
app.include_router(upload.router, prefix="/api/v1/upload", tags=["Upload"])
app.include_router(output.router, prefix="/api/v1/output", tags=["Output"])
app.include_router(application.router, prefix="/api/v1/application", tags=["Application"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])

# --- THE "BRAIN" ENDPOINT: ANALYZE RESUME ---
@app.post("/api/v1/ai/analyze", tags=["AI Engine"])
async def analyze_resume_against_job(
    file: UploadFile = File(...), 
    job_description: str = Form(...) # We use Form so we can send File + Text together
):
    """
    Step 1: Parse PDF to Markdown
    Step 2: Send to OpenRouter for Scoring
    """
    if not file.filename.lower().endswith(('.pdf', '.docx')):
        raise HTTPException(status_code=400, detail="Unsupported file format.")

    try:
        # 1. High-Fidelity Parsing
        content = await file.read()
        file_stream = io.BytesIO(content)
        result = converter.convert(file_stream)
        markdown_text = result.document.export_to_markdown()
        
        # 2. AI Scoring (Calling your ai_engine.py)
        ai_analysis = await get_resume_match_score(markdown_text, job_description)
        
        return {
            "filename": file.filename,
            "analysis": ai_analysis,
            "status": "success"
        }
    except Exception as e:
        print(f"Pipeline Error: {str(e)}")
        raise HTTPException(status_code=500, detail="AI Analysis failed. Check OpenRouter logs.")

@app.get("/")
@app.get("/health")
@app.get("/api/v1/health")
async def health_check():
    return {"status": "healthy"}
