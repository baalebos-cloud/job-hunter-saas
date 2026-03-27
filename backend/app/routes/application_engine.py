from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..database import SessionLocal
from ..models.application import Application
from ..schemas.application import ApplicationResponse
from ..dependencies.auth import get_current_user
from ..tasks.application_tasks import process_resume

router = APIRouter(prefix="/applications", tags=["Applications"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/submit/{job_id}", response_model=ApplicationResponse)
def submit_application(job_id: int, resume_text: str, job_description: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """
    Submit a resume for a job.
    Triggers async AI processing and notifications.
    """
    # Launch async task
    process_resume.delay(current_user.id, job_id, resume_text, job_description)

    return {"message": "Resume submitted successfully, processing started."}


@router.get("/", response_model=List[ApplicationResponse])
def get_user_applications(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """
    Fetch all applications for current user
    """
    applications = db.query(Application).filter(Application.user_id == current_user.id).all()
    return applications
