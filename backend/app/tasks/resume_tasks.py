from backend.app.celery_app import celery_app
from backend.app.services.resume_service import analyze_resume
from backend.app.services.notification_service import send_email_notification

@celery_app.task(name="process_resume_task")
def process_resume_task(file_content, filename, job_description, user_email, track, user):
    result = analyze_resume(
        file_content=file_content,
        filename=filename,
        job_description=job_description,
        track=track,
        user=user,
        user_email=user_email
)

    return result
