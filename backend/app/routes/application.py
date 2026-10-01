from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.dependencies.auth import get_current_user
from backend.app.models.application import Application
from backend.app.routes.jobs import apply_for_job, ApplicationRequest
router=APIRouter(tags=["Applications"])
@router.post("/apply/{job_id}")
def apply(job_id: int, payload: ApplicationRequest, db: Session=Depends(get_db), user=Depends(get_current_user)):
    return apply_for_job(job_id,payload,db,user)
@router.get("/")
def applications(db: Session=Depends(get_db), user=Depends(get_current_user)):
    return db.query(Application).filter(Application.user_id==user.id).all()
