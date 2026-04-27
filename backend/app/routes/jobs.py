from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.app.database import SessionLocal
from backend.app.models.job import Job
from backend.app.schemas.job import JobCreate, JobResponse
from backend.app.dependencies.auth import get_current_user

router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"]
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/", response_model=List[JobResponse])
def list_jobs(db: Session = Depends(get_db)):
    """
    FIX: Public endpoint — no auth required.
    The frontend shows the job feed to guests too.
    Previously required login, which caused 401 for all non-logged-in users.
    """
    jobs = db.query(Job).all()
    return jobs


@router.post("/", response_model=JobResponse)
def create_job(
    job: JobCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    new_job = Job(
        title=job.title,
        company=job.company,
        location=job.location,
        description=job.description,
        user_id=current_user.id
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    return new_job


@router.post("/{job_id}/apply")
def apply_for_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    FIX: New endpoint — frontend's onApply handler calls POST /jobs/{id}/apply.
    This was completely missing from the backend.
    """
    from backend.app.models.application import Application
    from datetime import datetime

    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check if already applied
    existing = db.query(Application).filter(
        Application.user_id == current_user.id,
        Application.job_id == job_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already applied for this job")

    application = Application(
        user_id=current_user.id,
        job_id=job_id,
        status="applied",
        created_at=datetime.utcnow()
    )
    db.add(application)
    db.commit()
    db.refresh(application)

    return {"message": "Application submitted successfully", "application_id": application.id}