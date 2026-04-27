from backend.app.celery_app import celery_app
from backend.app.models.application import Application
from backend.app.models.job import Job
from backend.app.models.resume import Resume
from backend.app.database import SessionLocal
from backend.app.services.matching_service import compute_match_score
from backend.app.services.application_service import process_application
import json

@celery_app.task
def process_application_task(application_id: int):
    return process_application(application_id)
    db = SessionLocal()
    try:
        application = db.query(Application).filter(Application.id == application_id).first()
        if not application:
            return

        job = db.query(Job).filter(Job.id == application.job_id).first()
        resume = db.query(Resume).filter(Resume.id == application.resume_id).first()

        if not job or not resume:
            return

        resume_data = json.loads(resume.parsed_data)

        match_result = compute_match_score(resume_data, job.description)

        application.match_score = match_result["score"]
        application.status = "processed"
        application.feedback = f"Missing skills: {', '.join(match_result['missing_skills'])}"

        db.commit()
    finally:
        db.close()
