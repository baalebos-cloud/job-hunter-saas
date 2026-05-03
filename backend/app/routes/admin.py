from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime
import os

from backend.app.database import get_db
from backend.app.dependencies.auth import get_current_user
from backend.app.models.user import User
from backend.app.models.job import Job
from backend.app.models.application import Application
from backend.app.models.resume import Resume

router = APIRouter(tags=["Admin"])


def require_admin(current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return current_user


@router.get("/stats")
def admin_stats(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return {
        "total_users":        db.query(User).count(),
        "total_jobs":         db.query(Job).count(),
        "total_applications": db.query(Application).count(),
        "total_resumes":      db.query(Resume).count(),
        "hr_users":           db.query(User).filter(User.is_hr == True).count(),
        "hr_posted_jobs":     db.query(Job).filter(Job.posted_by_hr == True).count(),
        "new_users_today":    db.query(User).filter(
            func.date(User.created_at) == datetime.utcnow().date()
        ).count(),
    }


@router.get("/users")
def list_users(
    skip: int = 0, limit: int = 50,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    users = db.query(User).order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    return [
        {
            "id": u.id, "email": u.email, "full_name": u.full_name,
            "career_track": u.career_track, "country": u.country,
            "is_admin": u.is_admin, "is_hr": u.is_hr,
            "company_name": u.company_name,
            "created_at": u.created_at,
            "applications": len(u.applications),
        }
        for u in users
    ]


@router.patch("/users/{user_id}/make-hr")
def make_hr(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_hr = True
    db.commit()
    return {"message": f"{user.email} is now an HR user"}


@router.patch("/users/{user_id}/make-admin")
def make_admin(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_admin = True
    db.commit()
    return {"message": f"{user.email} is now an admin"}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": "User deleted"}


@router.get("/jobs")
def list_all_jobs(
    skip: int = 0, limit: int = 50,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    jobs = db.query(Job).order_by(Job.scraped_at.desc()).offset(skip).limit(limit).all()
    return jobs


@router.delete("/jobs/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete(job)
    db.commit()
    return {"message": "Job deleted"}


@router.post("/scrape")
async def trigger_scrape(
    request: Request,
    admin: User = Depends(require_admin)
):
    """Trigger job scraper — admin only."""
    from fastapi.concurrency import run_in_threadpool
    from backend.app.utils.global_scraper import scrape_global_jobs
    result = await run_in_threadpool(scrape_global_jobs)
    return result


@router.get("/applications")
def list_applications(
    skip: int = 0, limit: int = 50,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    apps = db.query(Application).order_by(Application.created_at.desc()).offset(skip).limit(limit).all()
    return [
        {
            "id": a.id,
            "user_email": a.user.email if a.user else None,
            "job_title": a.job.title if a.job else None,
            "company": a.job.company if a.job else None,
            "status": a.status,
            "ats_score": a.ats_score,
            "created_at": a.created_at,
        }
        for a in apps
    ]
