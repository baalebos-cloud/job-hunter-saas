# =============================================================================
# backend/app/models/user.py
# =============================================================================
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.app.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}

    id                  = Column(Integer, primary_key=True, index=True)
    email               = Column(String, unique=True, index=True, nullable=False)
    full_name           = Column(String, nullable=True)
    hashed_password     = Column(String, nullable=False)
    career_track        = Column(String, nullable=True)
    country             = Column(String, nullable=True)
    is_admin            = Column(Boolean, default=False)
    is_hr               = Column(Boolean, default=False)
    company_name        = Column(String, nullable=True)
    is_verified         = Column(Boolean, default=False)
    verification_token  = Column(String, nullable=True)
    reset_token         = Column(String, nullable=True)
    reset_token_expires = Column(DateTime, nullable=True)

    # ── Profile fields (matches "My Profile" page) ────────────────────────────
    photo_url           = Column(String, nullable=True)
    phone                = Column(String, nullable=True)
    linkedin_url         = Column(String, nullable=True)
    available_for_work   = Column(Boolean, default=True)
    expected_pay_hourly  = Column(Float, nullable=True)
    about                = Column(Text, nullable=True)
    resume_url           = Column(String, nullable=True)   # link to latest uploaded resume file
    resume_filename      = Column(String, nullable=True)
    notice_period_days   = Column(Integer, nullable=True)
    city                 = Column(String, nullable=True)
    timezone             = Column(String, nullable=True)
    id_verified          = Column(Boolean, default=False)

    created_at          = Column(DateTime, default=datetime.utcnow)

    resumes            = relationship("Resume",          back_populates="owner")
    applications       = relationship("Application",     back_populates="user")
    outreach_messages  = relationship("OutreachMessage",  back_populates="user")
    subscription       = relationship("Subscription",    back_populates="user", uselist=False)
    referrals_made     = relationship("Referral", foreign_keys="Referral.referrer_id", back_populates="referrer")
    certified_skills    = relationship("CertifiedSkill",  back_populates="user", cascade="all, delete-orphan")
    other_skills        = relationship("OtherSkill",      back_populates="user", cascade="all, delete-orphan")
    education_entries    = relationship("Education",       back_populates="user", cascade="all, delete-orphan")
    experience_entries    = relationship("Experience",       back_populates="user", cascade="all, delete-orphan")
    languages           = relationship("UserLanguage",   back_populates="user", cascade="all, delete-orphan")


class CertifiedSkill(Base):
    """Verified/certified skills — e.g. from passing an ATS test or admin verification."""
    __tablename__ = "certified_skills"
    id       = Column(Integer, primary_key=True, index=True)
    user_id  = Column(Integer, ForeignKey("users.id"), nullable=False)
    name     = Column(String, nullable=False)
    verified = Column(Boolean, default=True)
    user     = relationship("User", back_populates="certified_skills")


class OtherSkill(Base):
    """Self-declared, unverified skills."""
    __tablename__ = "other_skills"
    id      = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name    = Column(String, nullable=False)
    user    = relationship("User", back_populates="other_skills")


class Education(Base):
    __tablename__ = "education_entries"
    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    degree       = Column(String, nullable=False)
    institution  = Column(String, nullable=False)
    start_date   = Column(String, nullable=True)   # stored as "Mon YYYY" text for display simplicity
    end_date     = Column(String, nullable=True)
    logo_url     = Column(String, nullable=True)
    user         = relationship("User", back_populates="education_entries")


class Experience(Base):
    __tablename__ = "experience_entries"
    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    title        = Column(String, nullable=False)
    company      = Column(String, nullable=False)
    start_date   = Column(String, nullable=True)
    end_date     = Column(String, nullable=True)
    description  = Column(Text, nullable=True)
    logo_url     = Column(String, nullable=True)
    user         = relationship("User", back_populates="experience_entries")


class UserLanguage(Base):
    __tablename__ = "user_languages"
    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False)
    name        = Column(String, nullable=False)     # e.g. "English"
    proficiency = Column(String, default="Advanced")  # Basic | Intermediate | Advanced | Fluent | Native
    user        = relationship("User", back_populates="languages")


class OutreachMessage(Base):
    __tablename__ = "outreach_messages"
    id             = Column(Integer, primary_key=True, index=True)
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=False)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    message        = Column(Text, nullable=False)
    sent_at        = Column(DateTime, default=datetime.utcnow)
    delivered      = Column(Boolean, default=False)

    user        = relationship("User",        back_populates="outreach_messages")
    application = relationship("Application", back_populates="outreach_messages")
