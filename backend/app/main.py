from fastapi import FastAPI, Response, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import io

from backend.app.database import Base, engine, get_db
from backend.app.routes import jobs, resume, auth, application, dashboard
from backend.app.models.resume import Resume
from backend.app.utils.pdf_generator import generate_optimized_resume
from backend.app.celery_app import celery_app

app = FastAPI(
    title="Baalebos Cloud AI",
    description="Global Talent Engine: AI Resume Analysis & Job Tracking",
    version="1.5.0"
)

# --- PRODUCTION CORS ---
# Added your AWS Load Balancer URL to the whitelist
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://baalebos.xyz",
    "https://www.baalebos.xyz",
    "http://jobhunter-alb-643561500.us-east-1.elb.amazonaws.com" 
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ROUTER REGISTRATION ---
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
app.include_router(resume.router, prefix="/resume", tags=["Resume"])
app.include_router(application.router, prefix="/application", tags=["Application"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])

# --- DOWNLOAD LOGIC ---
@app.get("/resume/download/{resume_id}", tags=["Resume"])
async def download_improved_resume(resume_id: int, db: Session = Depends(get_db)):
    resume_record = db.query(Resume).filter(Resume.id == resume_id).first()

    if not resume_record or not resume_record.analysis_data:
        raise HTTPException(status_code=404, detail="Resume analysis not yet completed or found.")

    # Momentum Strategy: Fetch the missing skills/improvements from the worker's JSON output
    improvements = resume_record.analysis_data.get("missing_list", [])

    # Generate the professional PDF
    pdf_buffer = generate_optimized_resume(
        filename=resume_record.filename,
        score=resume_record.ats_score,
        improvements=improvements
    )

    return Response(
        content=pdf_buffer.getvalue(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=Baalebos_Optimized_{resume_id}.pdf"
        }
    )

# --- SYSTEM LIFECYCLE ---
@app.on_event("startup")
async def startup_event():
    print("🚀 Baalebos Cloud API is starting...")
    # 1. Automatically create tables on AWS RDS if they don't exist
    Base.metadata.create_all(bind=engine)
    print("✅ RDS Tables: Verified/Created")

    # 2. Check Celery/Redis connectivity
    try:
        celery_app.control.ping(timeout=1)
        print("✅ Celery Worker: Connected")
    except Exception:
        print("⚠️ Celery Worker: Offline (Ensure Redis SG allows Port 6379)")

@app.get("/health", tags=["System"])
def health_check():
    return {"status": "online", "version": "1.5.0", "cloud": "AWS/EC2"}
