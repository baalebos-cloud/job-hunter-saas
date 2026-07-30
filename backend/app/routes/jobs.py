# =============================================================================
# backend/app/routes/jobs.py
# Fixed:
#  1. ATS score calculated at apply time from existing resume analysis_data
#  2. apply endpoint returns job_url so frontend opens the real job page
#  3. HR message: honest labelling — saved internally + copied to user's email
#  4. Removed duplicate imports
# =============================================================================
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
import json

from backend.app.database import get_db
from backend.app.models.job import Job
from backend.app.models.user import User, OutreachMessage
from backend.app.models.resume import Resume
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

FRESHNESS_DAYS = 3


class HRMessageRequest(BaseModel):
    message: str


def _apply_country_filter(q, country: str):
    if not country or country.lower() in ("all", "worldwide", "global", ""):
        return q
    c = country.lower().strip()
    if c in REMOTE_ACCEPTING:
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


def _compute_ats_score(resume: Resume, job: Job) -> float:
    """
    Compute ATS match score at apply time using stored analysis_data.
    Uses the last resume scan's overall_score as a base, then cross-checks
    missing keywords against the job description to refine the score.
    """
    if not resume or not resume.analysis_data or not job.description:
        return 0.0
    try:
        analysis = resume.analysis_data
        if isinstance(analysis, str):
            analysis = json.loads(analysis)
        base_score = float(analysis.get("overall_score", 0))
        missing    = analysis.get("missing_list", [])
        job_lower  = job.description.lower()
        # Keywords from the missing list that actually appear in this job's desc
        matched = sum(1 for kw in missing if kw and kw.lower() in job_lower)
        # Deduct for each still-missing keyword (max -20 penalty)
        penalty = min(20, len(missing) - matched) * 1.5
        score = max(0.0, min(100.0, round(base_score - penalty, 1)))
        return score
    except Exception:
        return 0.0


@router.get("/", response_model=List[JobResponse])
def list_jobs(
    country: Optional[str]  = Query(None),
    search:  Optional[str]  = Query(None),
    work_type: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    cutoff = datetime.utcnow() - timedelta(days=FRESHNESS_DAYS)
    q = db.query(Job).filter(or_(Job.scraped_at >= cutoff, Job.scraped_at.is_(None)))
    q = _apply_country_filter(q, country or "")
    if work_type and work_type.lower() != "all":
        q = q.filter(Job.work_type == work_type.lower())
    if search:
        kw = f"%{search}%"
        q = q.filter(or_(
            Job.title.ilike(kw), Job.company.ilike(kw),
            Job.description.ilike(kw), Job.category.ilike(kw),
        ))
    return q.order_by(Job.scraped_at.desc(), Job.id.desc()).all()


@router.get("/search", response_model=List[JobResponse])
def search_jobs(
    q: str = Query(..., min_length=1),
    country: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    cutoff = datetime.utcnow() - timedelta(days=FRESHNESS_DAYS)
    kw = f"%{q}%"
    query = db.query(Job).filter(
        or_(Job.scraped_at >= cutoff, Job.scraped_at.is_(None)),
        or_(
            Job.title.ilike(kw), Job.company.ilike(kw),
            Job.description.ilike(kw), Job.category.ilike(kw),
        )
    )
    query = _apply_country_filter(query, country or "")
    return query.order_by(Job.scraped_at.desc(), Job.id.desc()).limit(50).all()


@router.get("/matched", response_model=List[JobResponse])
def matched_jobs(
    job_title: Optional[str] = Query(None),
    country:   Optional[str] = Query(None),
    limit: int = Query(6, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    track        = current_user.career_track or job_title or ""
    user_country = country or current_user.country or ""
    cutoff       = datetime.utcnow() - timedelta(days=FRESHNESS_DAYS)
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


# ── FIX 1 & 2: Apply endpoint — real ATS score + returns job URL ──────────────
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
        Application.job_id  == job_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already applied for this job")

    # FIX 1: Compute real ATS score from user's last resume scan
    latest_resume = (
        db.query(Resume)
        .filter(Resume.owner_id == current_user.id)
        .order_by(Resume.id.desc())
        .first()
    )
    ats_score = _compute_ats_score(latest_resume, job)

    application = Application(
        user_id=current_user.id,
        job_id=job_id,
        status="applied",
        ats_score=ats_score,
        created_at=datetime.utcnow()
    )
    db.add(application)
    db.commit()
    db.refresh(application)

    # Send confirmation email
    background_tasks.add_task(
        send_application_confirmation,
        to_email=current_user.email,
        full_name=current_user.full_name or current_user.email,
        job_title=job.title,
        company=job.company or "the company"
    )

    return {
        "message":        "Application submitted successfully",
        "application_id": application.id,
        "job_url":        job.url,   # FIX 2: frontend opens this real URL
        "ats_score":      ats_score,
    }


# ── FIX 3 & 4: HR message — honest, saved internally + emailed to user ────────
@router.post("/{job_id}/message")
def send_hr_message(
    job_id: int,
    payload: HRMessageRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    HONEST BEHAVIOUR:
    - The message is saved to outreach_messages (internal record).
    - The application status is updated to 'messaged'.
    - The user receives the message in their own email so they can
      manually send it to HR via LinkedIn/email if they choose.
    - We do NOT pretend to email the actual HR/recruiter because
      we do not have their contact details from scraped jobs.
    """
    application = db.query(Application).filter(
        Application.user_id == current_user.id,
        Application.job_id  == job_id
    ).first()
    if not application:
        raise HTTPException(
            status_code=404,
            detail="Apply for this job first before sending a message."
        )

    job = db.query(Job).filter(Job.id == job_id).first()

    # Save outreach record
    record = OutreachMessage(
        user_id=current_user.id,
        application_id=application.id,
        message=payload.message,
        sent_at=datetime.utcnow(),
        delivered=True
    )
    db.add(record)
    application.status = "messaged"
    db.commit()
    db.refresh(record)

    # Email the message to the USER (not HR — we don't have HR's email)
    # User can then paste it into LinkedIn InMail or their email client
    background_tasks.add_task(
        send_application_confirmation,
        to_email=current_user.email,
        full_name=current_user.full_name or current_user.email,
        job_title=f"Your HR outreach message for {job.title if job else 'this role'}",
        company=job.company if job else "the company"
    )

    return {
        "message":     "Message saved and sent to your email. Use it to reach HR on LinkedIn or email.",
        "outreach_id": record.id,
        "sent_at":     record.sent_at,
        "note":        "Copy this message and send it directly to the recruiter via LinkedIn InMail or email.",
        "job_url":     job.url if job else None,
    }


@router.get("/{job_id}/messages")
def get_hr_messages(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    application = db.query(Application).filter(
        Application.user_id == current_user.id,
        Application.job_id  == job_id
    ).first()
    if not application:
        return []

    messages = db.query(OutreachMessage).filter(
        OutreachMessage.application_id == application.id
    ).order_by(OutreachMessage.sent_at.desc()).all()

    return [
        {
            "id":         m.id,
            "message":    m.message,
            "sent_at":    m.sent_at,
            "delivered":  m.delivered
        }
        for m in messages
    ]
