from sqlalchemy import JSON, Index, Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.app.database import Base

class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_active_work_type", "is_active", "work_type"),)

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    company = Column(String, index=True)
    location = Column(String, nullable=True)
    category = Column(String, index=True)
    url = Column(String, nullable=True)
    source = Column(String, nullable=True)
    description = Column(String, nullable=True)
    salary_range = Column(String, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    scraped_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    last_checked_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)
    # Unlike scraped_at, this never changes when a listing is refreshed.
    # Existing listings remain NULL after migration to avoid historical alerts.
    first_seen_at = Column(DateTime, default=datetime.utcnow, nullable=True, index=True)
    work_type = Column(String, nullable=True)  # remote | hybrid | onsite
    posted_by_hr = Column(Boolean, default=False)  # True = HR posted, False = scraped
    hr_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # HR who posted
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)  # employer workspace
    # Job board: one listing per role even when several boards carry it.
    dedupe_key = Column(String(300), nullable=True, index=True)   # normalised "title|company"
    skills = Column(JSON, nullable=True)                         # canonical skill names found in the posting
    employment_type = Column(String(32), nullable=True)          # Full-time | Part-time | Contract | Internship
    company_logo = Column(String(500), nullable=True)            # https URL from the source, when provided
    # Jobs posted on Baalebos: what the employer asks applicants (see services/application_form.py).
    application_form = Column(JSON, nullable=True)

    applications = relationship("Application", back_populates="job")
