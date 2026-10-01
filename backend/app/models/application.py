from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.app.database import Base

class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    ats_score = Column(Float, nullable=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=True)
    job_snapshot = Column(JSON, nullable=True)
    submission_method = Column(String, nullable=True)

    user = relationship("User", back_populates="applications")
    job = relationship("Job", back_populates="applications")
    outreach_messages = relationship("OutreachMessage", back_populates="application")