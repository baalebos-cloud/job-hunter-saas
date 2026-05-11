from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.dependencies.auth import get_current_user
from backend.app.models.user import User
from backend.app.models.job import Job
from backend.app.models.resume import Resume
from backend.app.services.outreach_service import generate_message

router = APIRouter(tags=["Outreach"])


class OutreachRequest(BaseModel):
    job_id: int
    resume_text: str = ""   # optional — if not provided, uses latest resume from DB


@router.post("/generate")
def create_outreach(
    payload: OutreachRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate a tailored HR outreach message for a specific job.
    Uses the job description already stored in the DB — no URL scraping.
    """
    job = db.query(Job).filter(Job.id == payload.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    resume_text = payload.resume_text

    # If no resume text provided, try to get from latest resume in DB
    if not resume_text:
        latest_resume = (
            db.query(Resume)
            .filter(Resume.owner_id == current_user.id)
            .order_by(Resume.id.desc())
            .first()
        )
        if latest_resume and latest_resume.analysis_data:
            resume_text = str(latest_resume.analysis_data)

    if not resume_text:
        raise HTTPException(
            status_code=400,
            detail="No resume text provided and no resume found in your account. Please upload a resume first."
        )

    try:
        message = generate_message(
            job_title=job.title,
            company=job.company or "the company",
            job_description=job.description or "",
            candidate_name=current_user.full_name or current_user.email,
            resume_text=resume_text,
        )
        return {
            "message": message,
            "job_title": job.title,
            "company": job.company,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
