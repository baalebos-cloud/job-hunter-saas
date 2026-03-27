from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

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
def list_jobs(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Fetch jobs belonging to the authenticated user.
    """

    jobs = db.query(Job).filter(Job.user_id == current_user.id).all()

    return jobs


@router.post("/", response_model=JobResponse)
def create_job(
    job: JobCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
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
