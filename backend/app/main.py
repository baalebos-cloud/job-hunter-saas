import io
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.app.database import Base, engine, get_db
# FIX: Removed 'upload' and 'output' — these route files do not exist and crash the server
from backend.app.routes import jobs, resume, auth, application, dashboard
from backend.app.ai_engine import get_resume_match_score

app = FastAPI(title="Baalebos Cloud AI")

# FIX: Use the origins list properly so localhost:5173 is allowed during local dev.
# When you go back to production, set ENVIRONMENT=production in .env and it restricts automatically.
import os
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

if ENVIRONMENT == "production":
    origins = [
        "https://baalebo.xyz",
        "https://www.baalebo.xyz",
    ]
else:
    # Local development — allow Vite dev server
    origins = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ROUTES ---
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["Jobs"])
app.include_router(resume.router, prefix="/api/v1/resume", tags=["Resume"])
app.include_router(application.router, prefix="/api/v1/application", tags=["Application"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])

# --- AI ANALYZE ENDPOINT ---
@app.post("/api/v1/ai/analyze", tags=["AI Engine"])
async def analyze_resume_against_job(
    file: UploadFile = File(...),
    job_description: str = Form(...)
):
    if not file.filename.lower().endswith(('.pdf', '.docx')):
        raise HTTPException(status_code=400, detail="Unsupported file format.")

    try:
        from docling.document_converter import DocumentConverter
        converter = DocumentConverter()
        content = await file.read()
        file_stream = io.BytesIO(content)
        result = converter.convert(file_stream)
        markdown_text = result.document.export_to_markdown()
        ai_analysis = await get_resume_match_score(markdown_text, job_description)
        return {"filename": file.filename, "analysis": ai_analysis, "status": "success"}
    except Exception as e:
        print(f"Pipeline Error: {str(e)}")
        raise HTTPException(status_code=500, detail="AI Analysis failed. Check OpenRouter logs.")

@app.get("/")
@app.get("/health")
@app.get("/api/v1/health")
async def health_check():
    return {"status": "healthy"}