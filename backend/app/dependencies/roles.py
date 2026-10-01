"""Backend authorization; email verification and HR approval are independent."""
import os
from fastapi import Depends, HTTPException
from backend.app.dependencies.auth import get_current_user

OWNER_EMAIL = "jayeolaoluwadamilare@gmail.com"

def is_owner(user):
    return bool(user and user.is_admin and user.is_verified and
                user.email.strip().lower() == os.getenv("ADMIN_EMAIL", OWNER_EMAIL).strip().lower())

def require_admin(current_user=Depends(get_current_user)):
    if not is_owner(current_user):
        raise HTTPException(403, "Owner access required.")
    return current_user

def require_hr(current_user=Depends(get_current_user)):
    if not is_owner(current_user) and not (current_user.is_hr and current_user.is_verified and current_user.hr_approved):
        raise HTTPException(403, "Approved HR access required.")
    return current_user
