from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from backend.app.database import get_db
from backend.app.models.job import Job
from backend.app.models.user import User, OutreachMessage
from backend.app.models.application import Application
from backend.app.schemas.job import JobCreate, JobResponse
from backend.app.dependencies.auth import get_current_user
from backend.app.services.notification_service import send_application_confirmation

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from backend.app.database import get_db
from backend.app.models.job import Job
from backend.app.models.user import User, OutreachMessage
from backend.app.models.application import Application
from backend.app.schemas.job import JobCreate, JobResponse
from backend.app.dependencies.auth import get_current_user
from backend.app.services.notification_service import send_application_confirmation

router = APIRouter(tags=["Jobs"])

# Countries that accept "Remote" / "Worldwide" jobs since no local boards exist
REMOTE_ACCEPTING = {
    "nigeria", "ghana", "kenya", "south africa", "ethiopia", "tanzania", "uganda",
    "rwanda", "senegal", "ivory coast", "cameroon", "zimbabwe", "zambia",
    "mozambique", "morocco", "tunisia", "algeria", "egypt",
    "india", "pakistan", "bangladesh", "sri lanka", "philippines", "vietnam",
    "indonesia", "thailand", "malaysia",
    "brazil", "argentina", "colombia", "chile", "peru", "mexico",
    "jamaica", "trinidad and tobago",
}

FRESHNESS_DAYS = 3  # Only show jobs scraped within last 3 days


class HRMessageRequest(BaseModel):
    message: str


def _apply_country_filter(q, country: str):
    """Smart country filter: exact match OR remote/worldwide for countries without local boards."""
    if not country or country.lower() in ("all", "worldwide", "global", ""):
        return q
    c = country.lower().strip()
    if c in REMOTE_ACCEPTING:
        # Show jobs in that country OR remote/worldwide jobs
        return q.filter(or_(
            Job.location.ilike(f"%{country}%"),
            Job.location.ilike("%remote%"),
            Job.location.ilike("%worldwide%"),
            Job.location.ilike("%global%"),
            Job.location.ilike("%africa%"),
            Job.location.ilike("%americas%"),
            Job.location.ilike("%asia%"),
        ))
    return q.filter(Job.location.ilike(f"%{country}%"))


@router.get("/", response_model=List[JobResponse])
def list_jobs(
    country: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    work_type: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    cutoff = datetime.utcnow() - timedelta(days=FRESHNESS_DAYS)
    q = db.query(Job).filter(
        or_(Job.scraped_at >= cutoff, Job.scraped_at.is_(None))
    )
    q = _apply_country_filter(q, country or "")
    if work_type and work_type.lower() != "all":
        q = q.filter(Job.work_type == work_type.lower())
    if search:
        kw = f"%{search}%"
        q = q.filter(or_(
            Job.title.ilike(kw),
            Job.company.ilike(kw),
            Job.description.ilike(kw),
            Job.category.ilike(kw),
        ))
    return q.order_by(Job.scraped_at.desc(), Job.id.desc()).all()


@router.get("/search", response_model=List[JobResponse])
def search_jobs(
    q: str = Query(..., min_length=1),
    country: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Real-time job search across title, company, description, category."""
    cutoff = datetime.utcnow() - timedelta(days=FRESHNESS_DAYS)
    kw = f"%{q}%"
    query = db.query(Job).filter(
        or_(Job.scraped_at >= cutoff, Job.scraped_at.is_(None)),
        or_(
            Job.title.ilike(kw),
            Job.company.ilike(kw),
            Job.description.ilike(kw),
            Job.category.ilike(kw),
        )
    )
    query = _apply_country_filter(query, country or "")
    return query.order_by(Job.scraped_at.desc(), Job.id.desc()).limit(50).all()


@router.get("/matched", response_model=List[JobResponse])
def matched_jobs(
    job_title: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    limit: int = Query(6, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns jobs matching the user's career_track + country preference."""
    track = current_user.career_track or job_title or ""
    user_country = country or current_user.country or ""

    cutoff = datetime.utcnow() - timedelta(days=FRESHNESS_DAYS)
    q = db.query(Job).filter(or_(Job.scraped_at >= cutoff, Job.scraped_at.is_(None)))
    q = _apply_country_filter(q, user_country)

    if track:
        jobs = q.filter(Job.category.ilike(f"%{track}%")).order_by(Job.id.desc()).limit(limit).all()
        if len(jobs) < limit:
            seen_ids = {j.id for j in jobs}
            for kw in track.split()[:3]:
                extra = q.filter(Job.title.ilike(f"%{kw}%")).order_by(Job.id.desc()).limit(limit).all()
                jobs += [j for j in extra if j.id not in seen_ids]
                seen_ids.update(j.id for j in extra)
                if len(jobs) >= limit:
                    break
        jobs = jobs[:limit]
    else:
        jobs = q.order_by(Job.id.desc()).limit(limit).all()

    return jobs


@router.post("/", response_model=JobResponse)
def create_job(
    job: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_job = Job(
        title=job.title, company=job.company,
        location=job.location, description=job.description,
        user_id=current_user.id
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    return new_job


@router.post("/{job_id}/apply")
def apply_for_job(
    job_id: int,
    background_tasks: BackgroundTasks,
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

    # Send confirmation email in background (non-blocking)
    background_tasks.add_task(
        send_application_confirmation,
        to_email=current_user.email,
        full_name=current_user.full_name or current_user.email,
        job_title=job.title,
        company=job.company or "the company"
    )

    return {
        "message": "Application submitted successfully",
        "application_id": application.id,
        "job_url": job.url  # frontend opens this in new tab
    }


@router.post("/{job_id}/message")
def send_hr_message(
    job_id: int,
    payload: HRMessageRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Send a direct message to HR for a job. Tracked in outreach_messages table."""
    application = db.query(Application).filter(
        Application.user_id == current_user.id,
        Application.job_id == job_id
    ).first()
    if not application:
        raise HTTPException(status_code=404, detail="Apply for this job first before messaging HR.")

    job = db.query(Job).filter(Job.id == job_id).first()

    record = OutreachMessage(
        user_id=current_user.id,
        application_id=application.id,
        message=payload.message,
        sent_at=datetime.utcnow(),
        delivered=True
    )
    db.add(record)

    # Update application status to show message was sent
    application.status = "messaged"
    db.commit()
    db.refresh(record)

    # Notify user their message was logged
    background_tasks.add_task(
        send_application_confirmation,
        to_email=current_user.email,
        full_name=current_user.full_name or current_user.email,
        job_title=f"HR Message Sent — {job.title if job else 'Role'}",
        company=job.company if job else "the company"
    )

    return {
        "message": "HR message sent and tracked successfully",
        "outreach_id": record.id,
        "sent_at": record.sent_at
    }


@router.get("/{job_id}/messages")
def get_hr_messages(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all HR messages sent for a specific job application."""
    application = db.query(Application).filter(
        Application.user_id == current_user.id,
        Application.job_id == job_id
    ).first()
    if not application:
        return []

    messages = db.query(OutreachMessage).filter(
        OutreachMessage.application_id == application.id
    ).order_by(OutreachMessage.sent_at.desc()).all()

    return [
        {
            "id": m.id,
            "message": m.message,
            "sent_at": m.sent_at,
            "delivered": m.delivered
        }
        for m in messages
    ]
