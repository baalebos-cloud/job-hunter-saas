from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from typing import List

# Import your shared dependency and security helper
from backend.app.database import get_db
from backend.app.dependencies import get_current_user 
# from backend.app.schemas.user import User  # Adjust based on your schema file name

# Service imports (Verified Syntax)
from backend.app.services.dashboard_service import get_dashboard_stats
from backend.app.services.job_service import list_jobs, get_job
from backend.app.services.application_service import applied_jobs, update_application_status

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
    dependencies=[Depends(get_current_user)] # Protections: Requires login for all routes below
)

# -----------------------------
# Dashboard analytics
# -----------------------------
@router.get("/stats")
def dashboard_stats(db: Session = Depends(get_db)):
    try:
        stats = get_dashboard_stats(db)
        if not stats:
            return {"active_applications": 0, "interviews": 0, "offers": 0}
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching dashboard stats")

# -----------------------------
# Jobs
# -----------------------------
@router.get("/jobs")
def get_all_jobs(db: Session = Depends(get_db)):
    return list_jobs(db)

@router.get("/jobs/{job_id}")
def job_detail(job_id: int, db: Session = Depends(get_db)):
    job = get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

# -----------------------------
# Applications
# -----------------------------
@router.get("/applied")
def list_applied_jobs(db: Session = Depends(get_db)):
    return applied_jobs(db)

@router.post("/jobs/{job_id}/status")
def set_application_status(
    job_id: int, 
    status_update: str, 
    db: Session = Depends(get_db)
):
    result = update_application_status(db, job_id, status_update)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to update status")
    return {"message": "Status updated successfully", "job_id": job_id, "new_status": status_update}
