from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from collections import defaultdict
import time

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.schemas.user import UserCreate, UserLogin, TokenResponse
from backend.app.services.auth_service import hash_password, verify_password, create_access_token
from backend.app.dependencies.auth import get_current_user
from backend.app.schemas.user import UserResponse

router = APIRouter(tags=["Authentication"])

# Brute force protection — track failed login attempts per IP
_failed_attempts: dict = defaultdict(list)
MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 300  # 5 minutes


def _check_brute_force(ip: str):
    now = time.time()
    # Clean attempts older than lockout window
    _failed_attempts[ip] = [t for t in _failed_attempts[ip] if now - t < LOCKOUT_SECONDS]
    if len(_failed_attempts[ip]) >= MAX_ATTEMPTS:
        remaining = int(LOCKOUT_SECONDS - (now - _failed_attempts[ip][0]))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed attempts. Try again in {remaining} seconds."
        )


def _record_failure(ip: str):
    _failed_attempts[ip].append(time.time())


def _clear_failures(ip: str):
    _failed_attempts.pop(ip, None)


def _get_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(user: UserCreate, request: Request, db: Session = Depends(get_db)):
    # Password strength validation
    if len(user.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered. Please login instead."
        )

    new_user = User(
        email=user.email.lower().strip(),
        full_name=user.full_name.strip(),
        hashed_password=hash_password(user.password),
        career_track=user.career_track,
        country=user.country,
        is_hr=user.is_hr or False,
        company_name=user.company_name,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_access_token({"sub": new_user.email})
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login", response_model=TokenResponse)
def login(user: UserLogin, request: Request, db: Session = Depends(get_db)):
    ip = _get_ip(request)
    _check_brute_force(ip)

    db_user = db.query(User).filter(User.email == user.email.lower().strip()).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        _record_failure(ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    _clear_failures(ip)
    token = create_access_token({"sub": db_user.email})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Returns the current logged-in user's profile."""
    return current_user


@router.post("/admin/login")
def admin_login(user: UserLogin, request: Request, db: Session = Depends(get_db)):
    """
    FIXED: Dedicated admin login endpoint.
    - Admins can login directly with their credentials
    - Returns is_admin flag for frontend routing to admin dashboard
    - No need to login as user first then manually navigate to /admin
    """
    ip = _get_ip(request)
    _check_brute_force(ip)

    db_user = db.query(User).filter(User.email == user.email.lower().strip()).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        _record_failure(ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Check if user is admin
    if not db_user.is_admin:
        _record_failure(ip)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin account required."
        )

    _clear_failures(ip)
    token = create_access_token({"sub": db_user.email})
    return {
        "access_token": token,
        "token_type": "bearer",
        "is_admin": True,
        "email": db_user.email,
        "full_name": db_user.full_name,
        "redirect": "/admin/dashboard"
    }
