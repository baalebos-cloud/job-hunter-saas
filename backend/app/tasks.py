import json
from celery import Celery
from sqlalchemy.orm import Session
from backend.app.database import SessionLocal
from backend.app.models.resume import Resume
from backend.app.models.application import Application
from backend.app.models.job import Job

# 🧠 The AI Engine: Keyword match & category breakdown
from backend.app.utils.ats_engine import analyze_detailed_ats
from backend.app.services.notification_service import send_email_notification

# --- CELERY CONFIGURATION ---
celery_app = Celery(
    "baalebos_tasks",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1"
)

# --- RESUME PROCESSING (MOMENTUM READY) ---
@celery_app.task(name="process_resume_task")
def process_resume_task(resume_id: int, file_content: bytes, job_description: str, job_title: str):
    """
    Production logic for Phase 6:
    1. Fetches existing DB record created by the 'upload' route.
    2. Runs AI Analysis (Detailed breakdown).
    3. Updates the record with JSON results for the PDF Generator.
    """
    db = SessionLocal()
    try:
        # 1. Fetch the placeholder record (this carries the user_id or None for guests)
        resume_record = db.query(Resume).filter(Resume.id == resume_id).first()
        if not resume_record:
            return {"status": "error", "message": "Resume record not found"}

        # 2. Execute AI Analysis
        # Returns: {overall_score, keywords_matched, keywords_missing, breakdown, missing_list}
        analysis_result = analyze_detailed_ats(file_content, resume_record.filename, job_description)

        # 3. Persist AI Data to Database
        # This JSON block is what the PDF Generator and AtsResultView will read
        resume_record.ats_score = analysis_result["overall_score"]
        resume_record.analysis_data = analysis_result 
        resume_record.status = "completed"
        
        db.commit()

        # 4. Notify if user is registered (has an email)
        if resume_record.user_id:
            # Note: You'd fetch the user's email from the User table here
            from backend.app.models.user import User
            user = db.query(User).filter(User.id == resume_record.user_id).first()
            if user and user.email:
                send_email_notification(
                    to_email=user.email,
                    subject=f"Baalebos AI: {job_title} Analysis Complete",
                    body=f"Your {analysis_result['overall_score']}% match analysis is ready to download."
                )

        return {
            "status": "completed", 
            "resume_id": resume_id, 
            "score": analysis_result["overall_score"]
        }

    except Exception as e:
        db.rollback()
        if resume_record:
            resume_record.status = "failed"
            db.commit()
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()

# --- APPLICATION PROCESSING ---
@celery_app.task(name="process_application_task")
def process_application_task(application_id: int):
    """
    Formalizes the match between a Job and a Resume for the Tracker.
    """
    db = SessionLocal()
    try:
        application = db.query(Application).filter(Application.id == application_id).first()
        if not application: return

        job = db.query(Job).filter(Job.id == application.job_id).first()
        resume = db.query(Resume).filter(Resume.id == application.resume_id).first()

        if job and resume:
            analysis = analyze_detailed_ats(resume.content, resume.filename, job.description)
            application.match_score = analysis["overall_score"]
            application.status = "processed"
            application.feedback = json.dumps(analysis["breakdown"])
            db.commit()
    finally:
        db.close()
