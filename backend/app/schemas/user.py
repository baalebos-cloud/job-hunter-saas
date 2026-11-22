from pydantic import BaseModel, EmailStr
from typing import Optional


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    career_track: Optional[str] = None
    country: Optional[str] = None
    is_hr: Optional[bool] = False
    company_name: Optional[str] = None
    ref_code: Optional[str] = None      # referral code from the invite link


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
