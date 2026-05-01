from backend.app.celery_app import celery_app
from backend.app.models.application import Application
from backend.app.models.job import Job
from backend.app.models.resume import Resume
from backend.app.database import SessionLocal
from backend.app.services.matching_service import compute_match_score
import json

@celery_app.task
def process_application_task(application_id: int):
    db = SessionLocal()
    try:
        application = db.query(Application).filter(Application.id == application_id).first()
        if not application:
            return

        job = db.query(Job).filter(Job.id == application.job_id).first()
        resume = db.query(Resume).filter(Resume.owner_id == application.user_id).order_by(Resume.id.desc()).first()

        if not job or not resume:
            return

        resume_data = json.loads(resume.parsed_data) if resume.parsed_data else {}
        match_result = compute_match_score(resume_data, job.description or "")

        application.ats_score = match_result.get("score", 0)
        application.status = "processed"
        db.commit()
    finally:
        db.close()
