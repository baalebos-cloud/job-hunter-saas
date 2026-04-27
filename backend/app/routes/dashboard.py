from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from typing import List

from backend.app.database import get_db
from backend.app.dependencies.auth import get_current_user  # FIX: was importing from wrong path
from backend.app.models.user import User
from backend.app.models.application import Application
from backend.app.services.dashboard_service import get_dashboard_stats
from backend.app.services.job_service import list_jobs, get_job
from backend.app.services.application_service import update_application_status

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
    dependencies=[Depends(get_current_user)]
)

# -----------------------------
# Dashboard analytics
# -----------------------------
@router.get("/stats")
def dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
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
def list_applied_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    FIX: Now filters by current_user.id so each user only sees their own applications.
    Previously called applied_jobs(db) with no filter — returned ALL users' data.
    """
    applications = db.query(Application).filter(
        Application.user_id == current_user.id
    ).all()
    return applications


@router.delete("/applied/{application_id}")
def delete_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    FIX: New endpoint — frontend's onDelete handler calls DELETE /dashboard/applied/{id}.
    This was completely missing from the backend, so the delete button did nothing end-to-end.
    """
    application = db.query(Application).filter(
        Application.id == application_id,
        Application.user_id == current_user.id  # Security: users can only delete their own
    ).first()

    if not application:
        raise HTTPException(
            status_code=404,
            detail="Application not found or you don't have permission to delete it"
        )

    db.delete(application)
    db.commit()
    return {"message": "Application deleted successfully", "id": application_id}


@router.post("/jobs/{job_id}/status")
def set_application_status(
    job_id: int,
    status_update: str,
    db: Session = Depends(get_db)
):
    result = update_application_status(db, job_id, status_update)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to update status")
    return {"message": "Status updated", "job_id": job_id, "new_status": status_update}