from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship
# CRITICAL: Use the full path so it matches alembic/env.py
from backend.app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)

    # Link to their resumes
    resumes = relationship("Resume", back_populates="owner", cascade="all, delete-orphan")
    
    # Link to their jobs (This solves the jobs.user_id dependency)
    jobs = relationship("Job", back_populates="owner", cascade="all, delete-orphan")
