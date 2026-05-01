from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from backend.app.database import get_db
from backend.app.models.job import Job
from backend.app.models.user import User
from backend.app.models.application import Application
from backend.app.schemas.job import JobCreate, JobResponse
from backend.app.dependencies.auth import get_current_user

router = APIRouter(tags=["Jobs"])


@router.get("/", response_model=List[JobResponse])
def list_jobs(db: Session = Depends(get_db)):
    """Public endpoint — no auth required."""
    return db.query(Job).order_by(Job.id.desc()).all()


@router.get("/matched", response_model=List[JobResponse])
def matched_jobs(
    job_title: Optional[str] = Query(None),
    limit: int = Query(6, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns jobs matching the user's career_track or the job_title from the analysis.
    Priority: career_track category match → title keyword match → latest jobs.
    """
    track = current_user.career_track or job_title or ""

    if track:
        jobs = db.query(Job).filter(
            Job.category.ilike(f"%{track}%")
        ).order_by(Job.id.desc()).limit(limit).all()

        if len(jobs) < limit:
            seen_ids = {j.id for j in jobs}
            for kw in track.split()[:3]:
                extra = db.query(Job).filter(
                    Job.title.ilike(f"%{kw}%")
                ).order_by(Job.id.desc()).limit(limit).all()
                jobs += [j for j in extra if j.id not in seen_ids]
                seen_ids.update(j.id for j in extra)
                if len(jobs) >= limit:
                    break

        jobs = jobs[:limit]
    else:
        jobs = db.query(Job).order_by(Job.id.desc()).limit(limit).all()

    return jobs


@router.post("/", response_model=JobResponse)
def create_job(
    job: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
    current_user: User = Depends(get_current_user)
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
        status="applied",
        created_at=datetime.utcnow()
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return {"message": "Application submitted successfully", "application_id": application.id}
