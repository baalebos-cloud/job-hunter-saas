from backend.app.celery_app import celery_app
from backend.app.database import SessionLocal
from backend.app.models.user import User
from backend.app.models.resume import Resume
from backend.app.utils.ats_engine import analyze_detailed_ats
from backend.app.services.notification_service import send_email_notification


@celery_app.task(name="process_resume_task")
def process_resume_task(resume_id: int, file_content: bytes, job_description: str, job_title: str):
    db = SessionLocal()
    try:
        resume_record = db.query(Resume).filter(Resume.id == resume_id).first()
        if not resume_record:
            return {"status": "error", "message": "Resume record not found"}

        analysis_result = analyze_detailed_ats(
            file_content=bytes(file_content) if not isinstance(file_content, bytes) else file_content,
            filename=resume_record.filename,
            job_description=job_description
        )

        resume_record.ats_score = analysis_result.get("overall_score", 0)
        resume_record.analysis_data = analysis_result
        db.commit()

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
