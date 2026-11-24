import re
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator


def _tidy(value: Optional[str], limit: int) -> Optional[str]:
    """Free text from the sign-up form: one line, no control characters, capped in length."""
    if value is None:
        return None
    value = re.sub(r'\s+', ' ', re.sub(r'[\x00-\x1f\x7f]', ' ', str(value))).strip()[:limit]
    return value or None


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
