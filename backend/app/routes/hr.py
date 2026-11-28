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


from backend.app.dependencies.roles import require_hr, is_owner  # noqa: F401  (kept for existing imports)
from backend.app.services.workspace import Member, job_for, member_for, require_permission, visible_jobs


class HRJobPost(BaseModel):
    title: str
    company: str
    location: str
    description: str
    salary_range: Optional[str] = None
    work_type: Optional[str] = "remote"
    category: Optional[str] = "Software Engineer"
    url: Optional[str] = None  # Application URL / company careers page
    application_form: Optional[dict] = None  # what applicants are asked (jobs without url only)


def _checked_form(raw):
    from backend.app.services.application_form import normalize_form
    try:
        return normalize_form(raw)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/jobs")
def post_job(
    job: HRJobPost,
    db: Session = Depends(get_db),
    member: Member = Depends(require_permission('post_jobs'))
):
    """HR posts a new job — appears immediately in the job feed.

    One active posting per role per company: a repeat is refused, and a
    scraped copy of the same role is closed so candidates see the employer's own."""
    from backend.app.utils.global_scraper import _keyed, dedupe_key
    hr_user = member.user
    form = _checked_form(job.application_form)
    company = job.company or member.company.name or hr_user.company_name or "Company"
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
        application_form=form,
        source="HR Posted",
        posted_by_hr=True,
        hr_user_id=hr_user.id,
        company_id=member.company.id,
        scraped_at=datetime.utcnow(),
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    return {"message": "Job posted successfully", "job_id": new_job.id, "job": new_job}


@router.get("/jobs")
def my_posted_jobs(
    db: Session = Depends(get_db),
    member: Member = Depends(member_for)
):
    """The company's jobs this person can see (hiring-team jobs only for hiring managers and interviewers)."""
    jobs = visible_jobs(db, member).order_by(Job.scraped_at.desc()).all()
    from backend.app.services.application_form import form_of
    return [{**{c.name: getattr(j, c.name) for c in Job.__table__.columns}, "application_form": form_of(j)} for j in jobs]


@router.put("/jobs/{job_id}/application-form")
def update_application_form(job_id: int, payload: dict, db: Session = Depends(get_db),
                            member: Member = Depends(require_permission('post_jobs'))):
    """Change what applicants are asked. Applications already sent keep the answers they were sent with."""
    job = job_for(db, member, job_id)
    job.application_form = _checked_form(payload)
    db.commit()
    return {"application_form": job.application_form}


@router.delete("/jobs/{job_id}")
def delete_my_job(
    job_id: int,
    db: Session = Depends(get_db),
    member: Member = Depends(require_permission('post_jobs'))
):
    job = job_for(db, member, job_id)
    db.delete(job)
    db.commit()
    return {"message": "Job deleted"}


@router.get("/jobs/{job_id}/applications")
def job_applications(
    job_id: int,
    db: Session = Depends(get_db),
    member: Member = Depends(member_for)
):
    """See all applicants for a specific job."""
    job_for(db, member, job_id)

    apps = db.query(Application).filter(
        Application.job_id == job_id
    ).order_by(Application.created_at.desc()).all()

    return [
        {
            "application_id": a.id,
            "resume_available": a.resume_id is not None and a.submission_method == "baalebos",
            "applicant_name": (a.applicant_details or {}).get("full_name") or (a.user.full_name if a.user else "Unknown"),
            "applicant_email": a.user.email if a.user else "Unknown",
            "applicant_country": (a.applicant_details or {}).get("country") or (a.user.country if a.user else None),
            "career_track": a.user.career_track if a.user else None,
            "ats_score": a.ats_score,
            "status": a.status,
            "applied_at": a.created_at,
            # What the candidate sent on Baalebos (None for older or external applications).
            "details": a.applicant_details,
            "answers": a.answers or [],
        }
        for a in apps
    ]


@router.get('/applications/{application_id}/resume')
def applicant_resume(application_id: int, db: Session = Depends(get_db), member: Member = Depends(member_for)):
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application or not application.job or application.submission_method != 'baalebos':
        raise HTTPException(404, 'Application not found')
    _application_job(db, member, application)
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
    member: Member = Depends(require_permission('move_candidates'))
):
    """HR updates application status — notifies the applicant."""
    valid_statuses = ["pending", "reviewed", "interview", "rejected", "offer"]
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {valid_statuses}")

    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    _application_job(db, member, app)
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
    member: Member = Depends(member_for)
):
    """HR dashboard stats (the jobs this person can see)."""
    my_jobs = visible_jobs(db, member).all()
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
        "company": member.company.name,
    }


def _application_job(db: Session, member: Member, application: Application) -> Job:
    """The application's job if this person may see it; otherwise 404 (as for any unknown application)."""
    try:
        return job_for(db, member, application.job_id)
    except HTTPException:
        raise HTTPException(404, 'Application not found') from None
