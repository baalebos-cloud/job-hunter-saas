# =============================================================================
# backend/app/routes/profile.py 
# Full profile management: bio, skills, education, experience, languages,
# photo, resume upload, account deletion.
# =============================================================================
import os
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List

from backend.app.database import get_db
from backend.app.dependencies.auth import get_current_user
from backend.app.models.user import (
    User, CertifiedSkill, OtherSkill, Education, Experience, UserLanguage
)

router = APIRouter(tags=["Profile"])

UPLOAD_DIR = os.getenv("OUTPUT_DIR", "/app/output")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://baalebo.xyz")

# Skills every user gets by default if none exist — matches the reference UI
DEFAULT_CERTIFIED_SKILLS = [
    "AWS Core Infrastructure",
    "Infrastructure as Code",
    "Linux Administration & Automation Scripting",
    "Cloud Networking & Security Best Practices",
]


# ── Schemas ────────────────────────────────────────────────────────────────────
class ProfileUpdate(BaseModel):
    full_name:           Optional[str]  = None
    career_track:        Optional[str]  = None
    country:             Optional[str]  = None
    phone:               Optional[str]  = None
    linkedin_url:        Optional[str]  = None
    available_for_work:  Optional[bool] = None
    expected_pay_hourly: Optional[float] = None
    about:               Optional[str]  = None
    notice_period_days:  Optional[int]  = None
    city:                Optional[str]  = None
    timezone:            Optional[str]  = None


class SkillIn(BaseModel):
    name: str


class EducationIn(BaseModel):
    degree:      str
    institution: str
    start_date:  Optional[str] = None
    end_date:    Optional[str] = None


class ExperienceIn(BaseModel):
    title:       str
    company:     str
    start_date:  Optional[str] = None
    end_date:    Optional[str] = None
    description: Optional[str] = None


class LanguageIn(BaseModel):
    name:        str
    proficiency: str = "Advanced"


def _serialize_profile(user: User) -> dict:
    return {
        "id":                  user.id,
        "full_name":           user.full_name,
        "email":               user.email,
        "career_track":        user.career_track,
        "country":             user.country,
        "phone":               user.phone,
        "linkedin_url":        user.linkedin_url,
        "photo_url":           user.photo_url,
        "available_for_work":  user.available_for_work,
        "expected_pay_hourly": user.expected_pay_hourly,
        "about":               user.about,
        "resume_url":          user.resume_url,
        "resume_filename":     user.resume_filename,
        "notice_period_days":  user.notice_period_days,
        "city":                user.city,
        "timezone":            user.timezone,
        "id_verified":         user.id_verified,
        "is_verified":         user.is_verified,
        "created_at":          user.created_at,
        "certified_skills":    [{"id": s.id, "name": s.name} for s in user.certified_skills],
        "other_skills":        [{"id": s.id, "name": s.name} for s in user.other_skills],
        "education":           [
            {"id": e.id, "degree": e.degree, "institution": e.institution,
             "start_date": e.start_date, "end_date": e.end_date, "logo_url": e.logo_url}
            for e in sorted(user.education_entries, key=lambda x: x.id, reverse=True)
        ],
        "experience":          [
            {"id": e.id, "title": e.title, "company": e.company,
             "start_date": e.start_date, "end_date": e.end_date,
             "description": e.description, "logo_url": e.logo_url}
            for e in sorted(user.experience_entries, key=lambda x: x.id, reverse=True)
        ],
        "languages":            [
            {"id": l.id, "name": l.name, "proficiency": l.proficiency}
            for l in user.languages
        ],
    }


# ── GET /profile/me ───────────────────────────────────────────────────────────
@router.get("/me")
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Seed default certified skills + default language on first visit
    if not current_user.certified_skills:
        for skill_name in DEFAULT_CERTIFIED_SKILLS:
            db.add(CertifiedSkill(user_id=current_user.id, name=skill_name, verified=True))
        db.commit()
        db.refresh(current_user)
    if not current_user.languages:
        db.add(UserLanguage(user_id=current_user.id, name="English", proficiency="Advanced"))
        db.commit()
        db.refresh(current_user)

    return _serialize_profile(current_user)


# ── PATCH /profile/me ─────────────────────────────────────────────────────────
@router.patch("/me")
def update_my_profile(
    payload: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    updates = payload.dict(exclude_unset=True)
    for field, value in updates.items():
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return _serialize_profile(current_user)


# ── POST /profile/photo ───────────────────────────────────────────────────────
@router.post("/photo")
async def upload_profile_photo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    allowed = [".jpg", ".jpeg", ".png", ".webp"]
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail="Only JPG, PNG, or WEBP images are allowed.")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large. Max 5MB.")

    os.makedirs(f"{UPLOAD_DIR}/avatars", exist_ok=True)
    filename = f"avatar_{current_user.id}_{uuid.uuid4().hex[:8]}{ext}"
    filepath = f"{UPLOAD_DIR}/avatars/{filename}"
    with open(filepath, "wb") as f:
        f.write(content)

    current_user.photo_url = f"{FRONTEND_URL}/api/v1/profile/photo/{filename}"
    db.commit()
    return {"photo_url": current_user.photo_url}


# ── POST /profile/resume-link ─────────────────────────────────────────────────
@router.post("/resume-link")
def link_resume_to_profile(
    resume_url: str,
    filename: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Link an already-uploaded optimized resume as the profile's public resume."""
    current_user.resume_url      = resume_url
    current_user.resume_filename = filename
    db.commit()
    return {"resume_url": resume_url, "filename": filename}


# ── SKILLS ────────────────────────────────────────────────────────────────────
@router.post("/skills/other")
def add_other_skill(
    payload: SkillIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Skill name required.")
    existing = db.query(OtherSkill).filter(
        OtherSkill.user_id == current_user.id,
        OtherSkill.name.ilike(payload.name.strip())
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Skill already added.")
    skill = OtherSkill(user_id=current_user.id, name=payload.name.strip())
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return {"id": skill.id, "name": skill.name}


@router.delete("/skills/other/{skill_id}")
def delete_other_skill(
    skill_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    skill = db.query(OtherSkill).filter(OtherSkill.id == skill_id, OtherSkill.user_id == current_user.id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found.")
    db.delete(skill)
    db.commit()
    return {"message": "Skill removed."}


# ── EDUCATION ─────────────────────────────────────────────────────────────────
@router.post("/education")
def add_education(
    payload: EducationIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    entry = Education(
        user_id=current_user.id,
        degree=payload.degree.strip(),
        institution=payload.institution.strip(),
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"id": entry.id, "degree": entry.degree, "institution": entry.institution,
            "start_date": entry.start_date, "end_date": entry.end_date}


@router.patch("/education/{entry_id}")
def update_education(
    entry_id: int,
    payload: EducationIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    entry = db.query(Education).filter(Education.id == entry_id, Education.user_id == current_user.id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Education entry not found.")
    entry.degree      = payload.degree.strip()
    entry.institution = payload.institution.strip()
    entry.start_date  = payload.start_date
    entry.end_date    = payload.end_date
    db.commit()
    return {"message": "Updated."}


@router.delete("/education/{entry_id}")
def delete_education(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    entry = db.query(Education).filter(Education.id == entry_id, Education.user_id == current_user.id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Education entry not found.")
    db.delete(entry)
    db.commit()
    return {"message": "Removed."}


# ── EXPERIENCE ────────────────────────────────────────────────────────────────
@router.post("/experience")
def add_experience(
    payload: ExperienceIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    entry = Experience(
        user_id=current_user.id,
        title=payload.title.strip(),
        company=payload.company.strip(),
        start_date=payload.start_date,
        end_date=payload.end_date,
        description=payload.description,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"id": entry.id}


@router.delete("/experience/{entry_id}")
def delete_experience(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    entry = db.query(Experience).filter(Experience.id == entry_id, Experience.user_id == current_user.id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Experience entry not found.")
    db.delete(entry)
    db.commit()
    return {"message": "Removed."}


# ── LANGUAGES ─────────────────────────────────────────────────────────────────
@router.post("/languages")
def add_language(
    payload: LanguageIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    existing = db.query(UserLanguage).filter(
        UserLanguage.user_id == current_user.id,
        UserLanguage.name.ilike(payload.name.strip())
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Language already added.")
    lang = UserLanguage(user_id=current_user.id, name=payload.name.strip(), proficiency=payload.proficiency)
    db.add(lang)
    db.commit()
    db.refresh(lang)
    return {"id": lang.id, "name": lang.name, "proficiency": lang.proficiency}


@router.delete("/languages/{lang_id}")
def delete_language(
    lang_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    lang = db.query(UserLanguage).filter(UserLanguage.id == lang_id, UserLanguage.user_id == current_user.id).first()
    if not lang:
        raise HTTPException(status_code=404, detail="Language not found.")
    db.delete(lang)
    db.commit()
    return {"message": "Removed."}


# ── DELETE /profile/me — delete account ───────────────────────────────────────
@router.delete("/me")
def delete_my_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db.delete(current_user)
    db.commit()
    return {"message": "Account deleted."}
