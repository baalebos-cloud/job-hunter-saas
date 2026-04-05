from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from backend.app.database import get_db
from backend.app.models.application import Application
from backend.app.models.job import Job
from backend.app.tasks import process_application_task

router = APIRouter(
    prefix="/applications",
    tags=["Applications"]
)

@router.post("/apply")
def apply_for_job(job_title: str, company: str, user_email: str, db: Session = Depends(get_db)):
    """
    Submits a new job application and triggers the background processing task.
    URL: /applications/apply
    """
    application = Application(
        job_title=job_title,
        company=company,
        user_email=user_email,
        status="pending"
    )

    db.add(application)
    db.commit()
    db.refresh(application)

    # Trigger Celery task for background processing (e.g., AI analysis)
    process_application_task.delay(application.id)

    return {"message": "Application submitted", "application_id": application.id}

@router.get("/")
def get_applications(user_email: str, db: Session = Depends(get_db)):
    """
    Retrieves all applications for a specific user.
    URL: /applications/
    """
    applications = db.query(Application).filter(Application.user_email == user_email).all()
    return applications
