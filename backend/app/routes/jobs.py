# =============================================================================
# backend/app/routes/jobs.py
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
    if not country or country.lower() in ("all", "worldwide", "global"):
        return q
    # Generic 'remote' is not evidence of eligibility in a specific country.
    return q.filter(or_(Job.location.ilike(f"%{country.strip()}%"),
                        Job.location.ilike("%worldwide%"), Job.location.ilike("%anywhere%")))


def _compute_ats_score(resume, job):
    if not resume or not resume.analysis_data:
        return None
    analysis = resume.analysis_data
    if analysis.get('job_description') != job.description:
        return None
    return analysis.get('overall_score')


@router.get("/", response_model=List[JobResponse])
def list_jobs(
    country: Optional[str]  = Query(None),
    search:  Optional[str]  = Query(None),
    work_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    cutoff = datetime.utcnow() - timedelta(days=FRESHNESS_DAYS)
    q = db.query(Job).filter(Job.is_active == True, or_(Job.scraped_at >= cutoff, Job.scraped_at.is_(None)))
    q = _apply_country_filter(q, country or "")
    if work_type and work_type.lower() != "all":
        q = q.filter(Job.work_type == work_type.lower())
    if search:
        kw = f"%{search}%"
        q = q.filter(or_(
            Job.title.ilike(kw), Job.company.ilike(kw),
            Job.description.ilike(kw), Job.category.ilike(kw),
        ))
    return q.order_by(Job.scraped_at.desc(), Job.id.desc()).offset(offset).limit(limit).all()


@router.get("/search", response_model=List[JobResponse])
def search_jobs(
    q: str = Query(..., min_length=1),
    country: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    cutoff = datetime.utcnow() - timedelta(days=FRESHNESS_DAYS)
    kw = f"%{q}%"
    query = db.query(Job).filter(
        Job.is_active == True,
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
    limit: int = Query(6, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    track        = current_user.career_track or job_title or ""
    user_country = country or current_user.country or ""
    cutoff       = datetime.utcnow() - timedelta(days=FRESHNESS_DAYS)
    q = db.query(Job).filter(Job.is_active == True, or_(Job.scraped_at >= cutoff, Job.scraped_at.is_(None)))
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
    from backend.app.dependencies.roles import require_hr
    require_hr(current_user)
    new_job = Job(
        title=job.title, company=job.company,
        location=job.location, description=job.description,
        user_id=current_user.id, hr_user_id=current_user.id,
        posted_by_hr=True, source='HR Posted'
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    return new_job


# ── FIX 1 & 2: Apply endpoint — real ATS score + returns job URL ──────────────
class ApplicationRequest(BaseModel):
    resume_id: Optional[str] = None


@router.post("/{job_id}/apply")
def apply_for_job(job_id: int, payload: ApplicationRequest, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    job = db.query(Job).filter(Job.id == job_id, Job.is_active == True).first()
    if not job:
        raise HTTPException(404, "Active job not found")
    selected = None
    if payload.resume_id:
        selected = db.query(Resume).filter(Resume.filename == f"optimized_{payload.resume_id}.pdf", Resume.owner_id == current_user.id).first()
        if not selected: raise HTTPException(404, "Resume not found")
        if (selected.analysis_data or {}).get('job_description') != job.description:
            raise HTTPException(409, "Tailor the selected resume to this job description before attaching it.")
    internal = bool(job.posted_by_hr and not job.url)
    if internal and not selected:
        raise HTTPException(422, "Select a resume tailored to this vacancy before submitting.")
    if not internal and (not job.url or not job.url.startswith(('https://','http://'))):
        raise HTTPException(422, "No valid employer application link is available.")
    app = db.query(Application).filter(Application.user_id == current_user.id, Application.job_id == job_id).first()
    if not app:
        app = Application(user_id=current_user.id, job_id=job_id)
        db.add(app)
    if app.status not in ('submitted_internal','reviewed','interview','offer','rejected','submitted_external'):
        app.status = 'submitted_internal' if internal else 'external_started'
        app.resume_id = selected.id if selected else None
        app.job_snapshot = {"title":job.title,"company":job.company,"description":job.description,"url":job.url}
        app.submission_method = 'baalebos' if internal else 'external_handoff'
        app.ats_score = _compute_ats_score(selected,job)
    db.commit(); db.refresh(app)
    return {"application_id": app.id, "status": app.status, "job_url":job.url,
            "message": "Received by the employer on Baalebos." if internal else "Open the employer form to complete your application. Employer receipt is not yet confirmed."}


@router.patch("/{job_id}/application-status")
def confirm_external(job_id: int, new_status: str, db: Session=Depends(get_db), current_user=Depends(get_current_user)):
    app=db.query(Application).filter(Application.job_id==job_id,Application.user_id==current_user.id).first()
    if not app: raise HTTPException(404,"Application not found")
    if app.submission_method != 'external_handoff' or new_status != 'submitted_external':
        raise HTTPException(400,"Only user confirmation of external submission is supported.")
    app.status='submitted_external'; db.commit()
    return {"status":app.status,"confirmation_source":"user"}


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
        delivered=False
    )
    db.add(record)
    # Drafting outreach does not change employer application status.
    db.commit()
    db.refresh(record)

    from backend.app.services.notification_service import send_email_notification
    background_tasks.add_task(send_email_notification, current_user.email,
                              "Your recruiter outreach draft", payload.message)

    return {
        "message":     "Message saved; a copy has been queued for your email. Use it to reach HR on LinkedIn or email.",
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


@router.get('/detail/{job_id}', response_model=JobResponse)
def job_detail(job_id: int, db: Session=Depends(get_db)):
    job=db.query(Job).filter(Job.id==job_id,Job.is_active==True).first()
    if not job: raise HTTPException(404,'Job not found')
    return job
