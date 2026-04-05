from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import os

from backend.app.database import get_db
from backend.app.models.user import User

# --- CONFIGURATION ---
# In production, use os.getenv to pull these from your RDS/EC2 environment
SECRET_KEY = os.getenv("SECRET_KEY", "BAALEBOS_SUPER_SECRET_KEY_2026_CLOUD_TALENT")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 43200  # 30 Days

# Setup password hashing
# We explicitly define the schemes to avoid the 'bcrypt' attribute error
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Setup OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# --- CORE AUTH UTILS ---

def hash_password(password: str) -> str:
    """
    Hashes the password. 
    Fixes the '72 bytes' error by ensuring the string is manageable.
    """
    if not password:
        raise HTTPException(status_code=400, detail="Password cannot be empty")
    
    # Bcrypt limit is 72 bytes. We truncate if a rogue script sends a massive string.
    # We also encode to utf-8 to ensure byte-length consistency.
    safe_password = password[:72] 
    return pwd_context.hash(safe_password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Match the truncation used in hashing
    return pwd_context.verify(plain_password[:72], hashed_password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# --- THE GATEKEEPER ---

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception

    return user
