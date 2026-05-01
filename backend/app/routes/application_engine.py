from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from backend.app.database import SessionLocal
from backend.app.models.application import Application
from backend.app.schemas.application import ApplicationResponse
from backend.app.dependencies.auth import get_current_user
from backend.app.tasks.application_tasks import process_application_task

router = APIRouter(tags=["Applications"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/submit/{job_id}")
def submit_application(
    job_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    application = Application(
        user_id=current_user.id,
        job_id=job_id,
        status="pending"
    )
    db.add(application)
    db.commit()
    db.refresh(application)

    process_application_task.delay(application.id)
    return {"message": "Resume submitted successfully, processing started.", "application_id": application.id}


@router.get("/", response_model=List[ApplicationResponse])
def get_user_applications(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return db.query(Application).filter(Application.user_id == current_user.id).all()
