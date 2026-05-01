from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from backend.app.database import get_db
from backend.app.models.application import Application
from backend.app.models.job import Job
from backend.app.dependencies.auth import get_current_user
from backend.app.tasks.application_tasks import process_application_task

router = APIRouter(tags=["Applications"])


@router.post("/apply/{job_id}")
def apply_for_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    existing = db.query(Application).filter(
        Application.user_id == current_user.id,
        Application.job_id == job_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already applied for this job")

    application = Application(
        user_id=current_user.id,
        job_id=job_id,
        status="pending"
    )
    db.add(application)
    db.commit()
    db.refresh(application)

    process_application_task.delay(application.id)

    return {"message": "Application submitted", "application_id": application.id}


@router.get("/")
def get_applications(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    applications = db.query(Application).filter(Application.user_id == current_user.id).all()
    return applications
