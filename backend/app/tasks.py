import json
import io
import fitz  # PyMuPDF
from celery import Celery
from sqlalchemy.orm import Session
from backend.app.database import SessionLocal
from backend.app.models.user import User
from backend.app.models.resume import Resume
from backend.app.utils.ats_engine import analyze_detailed_ats
from backend.app.services.notification_service import send_email_notification

# --- CELERY CONFIGURATION ---
# Note: In production, ensure these point to your Redis container name 'redis'
celery_app = Celery(
    "baalebos_tasks",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/1"
)

@celery_app.task(name="process_resume_task")
def process_resume_task(resume_id: int, file_content: bytes, job_description: str, job_title: str):
    db = SessionLocal()
    try:
        resume_record = db.query(Resume).filter(Resume.id == resume_id).first()
        if not resume_record:
            return {"status": "error", "message": "Resume record not found"}

        # --- NEW: PDF TO TEXT EXTRACTION ---
        # AI can't read bytes, so we extract the text first
        resume_text = ""
        try:
            doc = fitz.open(stream=file_content, filetype="pdf")
            for page in doc:
                resume_text += page.get_text()
        except Exception:
            # Fallback if it's not a PDF or parsing fails
            resume_text = "Could not extract text from file."

        # 2. Execute AI Analysis (Passing the extracted text)
        analysis_result = analyze_detailed_ats(resume_text, job_description, job_title)

        # 3. Persist AI Data
        resume_record.ats_score = analysis_result.get("overall_score", 0)
        resume_record.analysis_data = analysis_result
        # Update status if you have a status column
        # resume_record.status = "completed" 

        db.commit()

        # 4. Notify User
        if resume_record.owner_id:
            user = db.query(User).filter(User.id == resume_record.owner_id).first()
            if user and user.email:
                send_email_notification(
                    to_email=user.email,
                    subject=f"Baalebos AI: {job_title} Analysis Complete",
                    body=f"Your {analysis_result['overall_score']}% match analysis is ready."
                )

        return {"status": "completed", "resume_id": resume_id}

    except Exception as e:
        db.rollback()
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()
