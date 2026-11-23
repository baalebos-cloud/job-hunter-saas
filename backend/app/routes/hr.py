from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from pydantic import BaseModel

from backend.app.database import get_db
from backend.app.dependencies.auth import get_current_user
from backend.app.models.user import User
from backend.app.models.job import Job
from backend.app.models.application import Application
from backend.app.models.resume import Resume
from fastapi.responses import Response
from backend.app.services.notification_service import send_application_confirmation

router = APIRouter(tags=["HR"])


from backend.app.dependencies.roles import require_hr, is_owner


class HRJobPost(BaseModel):
    title: str
    company: str
    location: str
    description: str
    salary_range: Optional[str] = None
    work_type: Optional[str] = "remote"
    category: Optional[str] = "Software Engineer"
    url: Optional[str] = None  # Application URL / company careers page


@router.post("/jobs")
def post_job(
    job: HRJobPost,
    db: Session = Depends(get_db),
    hr_user: User = Depends(require_hr)
):
    """HR posts a new job — appears immediately in the job feed.

    One active posting per role per company: a repeat is refused, and a
    scraped copy of the same role is closed so candidates see the employer's own."""
    from backend.app.utils.global_scraper import _keyed, dedupe_key
    company = job.company or hr_user.company_name or "Company"
    key = dedupe_key(job.title, company, job.location)
    if _keyed(key):
        from sqlalchemy import or_
        # Rows saved before keys existed have none until the next clean-up: compare those by recomputing.
        candidates = db.query(Job).filter(Job.is_active == True,  # noqa: E712
                                          or_(Job.dedupe_key == key, Job.dedupe_key.is_(None))).all()
        twins = [t for t in candidates if (t.dedupe_key or dedupe_key(t.title, t.company, t.location)) == key]
        if any(t.posted_by_hr for t in twins):
            raise HTTPException(409, "This role is already posted for this company. Edit or close the existing "
                                     "posting instead of creating a duplicate.")
        for twin in twins:
            twin.is_active = False
    new_job = Job(
        title=job.title,
        company=company,
        dedupe_key=key,
        location=job.location,
        description=job.description,
        salary_range=job.salary_range,
        work_type=job.work_type,
        category=job.category,
        url=job.url,
        source="HR Posted",
        posted_by_hr=True,
        hr_user_id=hr_user.id,
        scraped_at=datetime.utcnow(),
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    return {"message": "Job posted successfully", "job_id": new_job.id, "job": new_job}


@router.get("/jobs")
def my_posted_jobs(
    db: Session = Depends(get_db),
    hr_user: User = Depends(require_hr)
):
    """Get all jobs posted by this HR user."""
    jobs = db.query(Job).filter(
        Job.hr_user_id == hr_user.id
    ).order_by(Job.scraped_at.desc()).all()
    return jobs


@router.delete("/jobs/{job_id}")
def delete_my_job(
    job_id: int,
    db: Session = Depends(get_db),
    hr_user: User = Depends(require_hr)
):
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.hr_user_id == hr_user.id
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or not yours")
    db.delete(job)
    db.commit()
    return {"message": "Job deleted"}


@router.get("/jobs/{job_id}/applications")
def job_applications(
    job_id: int,
    db: Session = Depends(get_db),
    hr_user: User = Depends(require_hr)
):
    """See all applicants for a specific job."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.hr_user_id != hr_user.id and not is_owner(hr_user):
        raise HTTPException(404, "Job not found")

    apps = db.query(Application).filter(
        Application.job_id == job_id
    ).order_by(Application.created_at.desc()).all()

    return [
        {
            "application_id": a.id,
            "resume_available": a.resume_id is not None and a.submission_method == "baalebos",
            "applicant_name": a.user.full_name if a.user else "Unknown",
            "applicant_email": a.user.email if a.user else "Unknown",
            "applicant_country": a.user.country if a.user else None,
            "career_track": a.user.career_track if a.user else None,
            "ats_score": a.ats_score,
            "status": a.status,
            "applied_at": a.created_at,
        }
        for a in apps
    ]


@router.get('/applications/{application_id}/resume')
def applicant_resume(application_id: int, db: Session = Depends(get_db), hr_user: User = Depends(require_hr)):
    application = db.query(Application).filter(Application.id == application_id).first()
    if (not application or not application.job or application.submission_method != 'baalebos'
            or (application.job.hr_user_id != hr_user.id and not is_owner(hr_user))):
        raise HTTPException(404, 'Application not found')
    resume = db.query(Resume).filter(Resume.id == application.resume_id,
                                     Resume.owner_id == application.user_id).first()
    if not resume:
        raise HTTPException(404, 'Resume not found')
    from backend.app.services.resume_storage import load_pdf
    return Response(load_pdf(resume), media_type='application/pdf', headers={
        'Content-Disposition': 'inline; filename="Applicant_Resume.pdf"', 'Cache-Control': 'private, no-store'})


@router.patch("/applications/{application_id}/status")
def update_application_status(
    application_id: int,
    new_status: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    hr_user: User = Depends(require_hr)
):
    """HR updates application status — notifies the applicant."""
    valid_statuses = ["pending", "reviewed", "interview", "rejected", "offer"]
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {valid_statuses}")

    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    if not app.job or (app.job.hr_user_id != hr_user.id and not is_owner(hr_user)):
        raise HTTPException(404, "Application not found")
    app.status = new_status
    db.commit()

    # Notify applicant
    if app.user and new_status in ("interview", "offer"):
        background_tasks.add_task(
            send_application_confirmation,
            to_email=app.user.email,
            full_name=app.user.full_name or app.user.email,
            job_title=f"Status Update: {new_status.upper()} — {app.job.title if app.job else 'Role'}",
            company=app.job.company if app.job else "the company"
        )

    return {"message": f"Status updated to {new_status}", "application_id": application_id}


@router.get("/dashboard")
def hr_dashboard(
    db: Session = Depends(get_db),
    hr_user: User = Depends(require_hr)
):
    """HR dashboard stats."""
    my_jobs = db.query(Job).filter(Job.hr_user_id == hr_user.id).all()
    job_ids = [j.id for j in my_jobs]
    total_apps = db.query(Application).filter(Application.job_id.in_(job_ids)).count() if job_ids else 0
    interviews = db.query(Application).filter(
        Application.job_id.in_(job_ids),
        Application.status == "interview"
    ).count() if job_ids else 0

    return {
        "total_jobs_posted": len(my_jobs),
        "total_applications": total_apps,
        "interviews_scheduled": interviews,
        "company": hr_user.company_name or hr_user.full_name,
    }
