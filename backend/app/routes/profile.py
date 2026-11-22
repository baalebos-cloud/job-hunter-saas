# =============================================================================
# backend/app/routes/profile.py 
# Full profile management: bio, skills, education, experience, languages,
# photo, resume upload, account deletion.
# =============================================================================
import os
import re
import uuid
from datetime import datetime
from fastapi import Request, Response, APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from typing import Literal

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
    job_alerts_enabled:   Optional[bool] = None
    job_alert_work_type:  Optional[Literal["all", "remote", "hybrid", "onsite"]] = None
    job_alert_frequency:  Optional[Literal["daily", "weekly"]] = None
    job_alert_min_match:  Optional[Literal[0, 50, 70]] = None


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
        "is_hr":               user.is_hr,
        "is_admin":            user.is_admin,
        "job_alerts_enabled":   user.job_alerts_enabled,
        "job_alert_work_type":  user.job_alert_work_type,
        "job_alert_frequency":  user.job_alert_frequency or "daily",
        "job_alert_min_match":  user.job_alert_min_match or 0,
        "created_at":          user.created_at,
        "certified_skills":    [{"id": s.id, "name": s.name} for s in user.certified_skills if s.verified and s.name not in DEFAULT_CERTIFIED_SKILLS],
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
    return _serialize_profile(current_user)


# ── PATCH /profile/me ─────────────────────────────────────────────────────────
@router.patch("/me")
def update_my_profile(
    payload: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    updates = payload.dict(exclude_unset=True)
    # Nullable PATCH fields cannot erase database NOT NULL consent settings.
    if any(field in updates and updates[field] is None for field in ("job_alerts_enabled", "job_alert_work_type",
                                                                   "job_alert_frequency", "job_alert_min_match")):
        raise HTTPException(422, "Choose a valid job alert setting.")
    if updates.get("job_alerts_enabled"):
        if current_user.is_hr or current_user.is_admin:
            raise HTTPException(422, "Job alerts are for job seeker accounts.")
        track = updates.get("career_track", current_user.career_track)
        if not current_user.is_verified or not track or not track.strip():
            raise HTTPException(422, "Verify your email and add a career track before enabling job alerts.")
        if not current_user.job_alerts_enabled:
            current_user.job_alerts_enabled_at = datetime.utcnow()
    for field, value in updates.items():
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return _serialize_profile(current_user)


# ── Profile photo ─────────────────────────────────────────────────────────────
PHOTO_SIZE = 512
PHOTO_MAX_BYTES = 5 * 1024 * 1024


def _process_photo(content: bytes) -> bytes:
    """Validate and re-encode: square centre crop, 512 px, WebP, no metadata."""
    from io import BytesIO
    from PIL import Image, ImageOps, UnidentifiedImageError
    Image.MAX_IMAGE_PIXELS = 40_000_000
    try:
        image = Image.open(BytesIO(content))
        if image.format not in ("JPEG", "PNG", "WEBP"):
            raise HTTPException(400, "Only JPG, PNG or WebP images are allowed.")
        image = ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(400, "This file is not a readable image.")
    image = ImageOps.fit(image, (PHOTO_SIZE, PHOTO_SIZE), method=Image.LANCZOS)
    out = BytesIO()
    image.save(out, format="WEBP", quality=85, method=4)
    return out.getvalue()


@router.post("/photo")
async def upload_profile_photo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """The dashboard sends an already-cropped image; the server still validates,
    crops to a square and re-encodes it."""
    from backend.app.models.user import ProfilePhoto
    content = await file.read(PHOTO_MAX_BYTES + 1)
    if len(content) > PHOTO_MAX_BYTES:
        raise HTTPException(400, "Image too large. Max 5 MB.")
    data = _process_photo(content)
    photo = db.get(ProfilePhoto, current_user.id) or ProfilePhoto(user_id=current_user.id)
    photo.token = uuid.uuid4().hex
    photo.content, photo.content_type, photo.updated_at = data, "image/webp", datetime.utcnow()
    db.add(photo)
    current_user.photo_url = f"/api/v1/profile/photo/{photo.token}.webp"
    db.commit()
    return {"photo_url": current_user.photo_url}


@router.delete("/photo")
def delete_profile_photo(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from backend.app.models.user import ProfilePhoto
    photo = db.get(ProfilePhoto, current_user.id)
    if photo:
        db.delete(photo)
    current_user.photo_url = None
    db.commit()
    return {"photo_url": None}


@router.get("/photo/{token}.webp")
def get_profile_photo(token: str, db: Session = Depends(get_db)):
    """Public, unguessable URL (new token per upload), cached by browsers."""
    from fastapi import Response
    from backend.app.models.user import ProfilePhoto
    if not re.fullmatch(r"[0-9a-f]{32}", token):
        raise HTTPException(404, "Photo not found.")
    photo = db.query(ProfilePhoto).filter(ProfilePhoto.token == token).first()
    if not photo:
        raise HTTPException(404, "Photo not found.")
    return Response(photo.content, media_type=photo.content_type,
                    headers={"Cache-Control": "public, max-age=31536000, immutable",
                             "X-Content-Type-Options": "nosniff"})


# ── POST /profile/resume-link ─────────────────────────────────────────────────
@router.post("/resume-link")
def link_resume_to_profile(
    resume_url: str,
    filename: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Link an already-uploaded optimized resume as the profile's public resume."""
    from backend.app.utils.url_safety import validate_public_https_url, UnsafeUrl
    try:
        resume_url = validate_public_https_url(resume_url)
    except UnsafeUrl as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    filename = (filename or '').strip()[:255]
    if not filename or any(c in filename for c in '/\\\x00'):
        raise HTTPException(status_code=422, detail="Provide a plain file name.")
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


@router.patch("/experience/{entry_id}")
def update_experience(
    entry_id: int,
    payload: ExperienceIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    entry = db.query(Experience).filter(Experience.id == entry_id, Experience.user_id == current_user.id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Experience not found.")
    for field, value in payload.dict().items():
        setattr(entry, field, value)
    db.commit()
    return {"id": entry.id, "title": entry.title, "company": entry.company, "start_date": entry.start_date,
            "end_date": entry.end_date, "description": entry.description}


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
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """GDPR Art. 17: transactional erasure of the account and every linked
    record, stored resume objects and avatar; sessions are revoked."""
    from backend.app.routes.privacy import erase_and_revoke
    from backend.app.services.auth_service import clear_refresh_cookie
    if current_user.role == "super_admin":
        from backend.app.models.user import User as UserModel
        others = db.query(UserModel).filter(UserModel.role == "super_admin", UserModel.id != current_user.id).count()
        if not others:
            raise HTTPException(status_code=409, detail="Assign another super_admin before deleting this account.")
    result = erase_and_revoke(request, db, current_user, requested_by="self")
    clear_refresh_cookie(response)
    return {"message": "Account deleted.", "objects_pending": result["objects_pending"]}
