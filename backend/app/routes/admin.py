from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime
import os
import json
from threading import Lock
from time import monotonic

from backend.app.database import get_db
from backend.app.dependencies.auth import get_current_user
from backend.app.models.user import User
from backend.app.models.job import Job
from backend.app.models.application import Application
from backend.app.models.resume import Resume

router = APIRouter(tags=["Admin"])


from backend.app.dependencies.roles import require_admin


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
    if not user.is_verified:
        raise HTTPException(400, "Verify the account email before approval")
    user.is_hr = True
    user.hr_approved = True
    db.commit()
    return {"message": f"{user.email} is now an HR user"}


@router.patch("/users/{user_id}/make-admin")
def make_admin(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.email.strip().lower() != admin.email.strip().lower():
        raise HTTPException(403, "Only the owner may be an administrator")
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

# One synthetic probe at a time per process; avoid accidental repeated clicks.
_probe_lock = Lock()
_probe_last_started = None


@router.post("/resume-diagnostic")
def resume_diagnostic(admin: User = Depends(require_admin)):
    """Owner-only, synthetic input; no database writes or candidate resumes."""
    global _probe_last_started
    if not _probe_lock.acquire(blocking=False):
        raise HTTPException(429, "A diagnostic is already running. Please wait.")
    try:
        now = monotonic()
        if _probe_last_started is not None and now - _probe_last_started < 60:
            raise HTTPException(429, "Wait one minute before running another diagnostic.")
        _probe_last_started = now
        from backend.app.utils.ats_engine import get_client
        from backend.scripts.diagnose_resume_provider import run_probe
        events = []
        try:
            client, model = get_client()
            result = run_probe(client, model, emit=lambda line: events.append(json.loads(line)))
        except Exception as exc:
            # Never expose credential-bearing exception messages or tracebacks.
            events.append({"result": "setup_failed", "error": type(exc).__name__})
            result = 2
        from fastapi.responses import JSONResponse
        return JSONResponse({"passed": result == 0, "events": events},
                            headers={"Cache-Control": "no-store"})
    finally:
        _probe_lock.release()
