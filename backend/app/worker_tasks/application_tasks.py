from backend.app.celery_app import celery_app
from backend.app.models.application import Application
from backend.app.models.job import Job
from backend.app.models.resume import Resume
from backend.app.database import SessionLocal
from backend.app.services.matching_service import compute_match_score
import json

@celery_app.task(name='backend.app.worker_tasks.application_tasks.process_application_task')
def process_application_task(application_id):
    db = SessionLocal()
    try:
        application = db.query(Application).filter(Application.id == application_id).first()
        if not application:
            return f"Error: Application {application_id} not found"

        job = db.query(Job).filter(Job.id == application.job_id).first()
        resume = db.query(Resume).filter(Resume.id == application.resume_id).first()

        if not job or not resume:
            return "Error: Missing Job or Resume data"

        resume_data = json.loads(resume.parsed_data)
        match_result = compute_match_score(resume_data, job.description)

        application.match_score = match_result["score"]
        application.status = "processed"
        application.feedback = f"Missing skills: {', '.join(match_result['missing_skills'])}"

        db.commit()
        return f"Success: Scored {match_result['score']}% for application {application_id}"
    except Exception as e:
        db.rollback()
        return f"Failure: {str(e)}"
    finally:
        db.close()
