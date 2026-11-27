import re
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator


def _tidy(value: Optional[str], limit: int) -> Optional[str]:
    """Free text from the sign-up form: one line, no control characters, capped in length."""
    if value is None:
        return None
    value = re.sub(r'\s+', ' ', re.sub(r'[\x00-\x1f\x7f]', ' ', str(value))).strip()[:limit]
    return value or None


def _tidy_list(values, limit: int, length: int, what: str):
    """Trim, drop blanks and repeats (any letter case), keep order; at most ``limit``."""
    if not values:
        return None
    out, seen = [], set()
    for value in values:
        text = _tidy(value, length)
        if text and text.lower() not in seen:
            seen.add(text.lower()); out.append(text)
    if len(out) > limit:
        raise ValueError(f'Choose up to {limit} {what}.')
    return out or None


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    career_track: Optional[str] = None
    country: Optional[str] = None
    is_hr: Optional[bool] = False
    company_name: Optional[str] = None
    ref_code: Optional[str] = None      # referral code from the invite link
    # First-touch campaign tags captured by the website (counts only in reports).
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    referrer: Optional[str] = None
    # Several choices at sign-up. The first track becomes career_track.
    career_tracks: Optional[list[str]] = None      # up to 3
    work_types: Optional[list[str]] = None         # remote | hybrid | onsite
    work_countries: Optional[list[str]] = None     # up to 5 countries open to working in

    @field_validator('career_tracks')
    @classmethod
    def _tracks(cls, value):
        return _tidy_list(value, 3, 80, 'career tracks')

    @field_validator('work_countries')
    @classmethod
    def _countries(cls, value):
        return _tidy_list(value, 5, 60, 'countries')

    @field_validator('work_types')
    @classmethod
    def _work_types(cls, value):
        if not value:
            return None
        allowed = ('remote', 'hybrid', 'onsite')
        picked = [w for w in allowed if w in {str(v).strip().lower() for v in value}]
        if len(picked) != len({str(v).strip().lower() for v in value}):
            raise ValueError('Work type must be remote, hybrid or onsite.')
        return picked

    # Career track is typed freely (suggestions are offered); country comes from the list.
    @field_validator('career_track')
    @classmethod
    def _track(cls, value):
        return _tidy(value, 80)

    @field_validator('country')
    @classmethod
    def _country(cls, value):
        return _tidy(value, 60)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    career_track: Optional[str] = None
    country: Optional[str] = None
    is_admin: Optional[bool] = False
    is_hr: Optional[bool] = False
    role: Optional[str] = None
    permissions: list[str] = []
    mfa_enabled: bool = False
    photo_url: Optional[str] = None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: Optional[int] = None
    # Set instead of access_token when the account uses two-step verification.
    mfa_required: Optional[bool] = None
    mfa_token: Optional[str] = None
