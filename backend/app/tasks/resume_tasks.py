from backend.app.celery_app import celery_app
from backend.app.services.resume_service import analyze_resume

# 🚀 MATCHING NAME AND 5 ARGUMENTS
@celery_app.task(name="process_resume_task")
def process_resume_task(file_content, filename, job_description, user_id, job_title):
    # Mapping job_title to 'track' for the service
    result = analyze_resume(
        file_content=file_content,
        filename=filename,
        job_description=job_description,
        track=job_title,
        user_id=user_id
    )
    return result
