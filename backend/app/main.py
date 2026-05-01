import io
import os
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel # Added for AnalysisRequest

from backend.app.database import Base, engine, get_db
from backend.app.routes import jobs, resume, auth, application, dashboard
from backend.app.services.ai_service import ai_engine

# Auto-create all tables on startup (safe — skips existing tables)
from backend.app.models.user import User  # noqa: F401
from backend.app.models.job import Job  # noqa: F401
from backend.app.models.resume import Resume  # noqa: F401
from backend.app.models.application import Application  # noqa: F401
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Baalebos Cloud AI")

# --- SCHEMAS ---
class AnalysisRequest(BaseModel):
    resume_text: str
    job_description: str

# --- CORS SETUP ---
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
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
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
async def analyze_resume_against_job(payload: AnalysisRequest):
    try:
        result = await ai_engine.analyze_resume(payload.resume_text, payload.job_description)
        return result  
    except Exception as e:
        print(f"Detailed Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
@app.get("/health")
@app.get("/api/v1/health")
async def health_check():
    return {"status": "healthy"}