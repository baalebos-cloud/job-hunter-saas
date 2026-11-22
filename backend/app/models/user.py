# =============================================================================
# backend/app/models/user.py
# =============================================================================
from sqlalchemy import JSON, Index, Column, Integer, String, DateTime, Text, ForeignKey, Boolean, Float, LargeBinary
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.app.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (Index('ix_users_verification_token', 'verification_token'),
                      Index('ix_users_reset_token', 'reset_token'),
                      {'extend_existing': True})

    id                  = Column(Integer, primary_key=True, index=True)
    email               = Column(String, unique=True, index=True, nullable=False)
    full_name           = Column(String, nullable=True)
    hashed_password     = Column(String, nullable=False)
    career_track        = Column(String, nullable=True)
    country             = Column(String, nullable=True)
    is_admin            = Column(Boolean, default=False)
    referral_code       = Column(String, unique=True, nullable=True)
    is_hr               = Column(Boolean, default=False)
    hr_approved         = Column(Boolean, default=False, nullable=False)
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
    job_alerts_enabled   = Column(Boolean, default=False, nullable=False)
    job_alerts_enabled_at = Column(DateTime, nullable=True)
    job_alert_work_type  = Column(String, default="all", nullable=False)
    job_alert_frequency  = Column(String(10), default="daily", server_default="daily", nullable=False)  # daily | weekly
    job_alert_min_match  = Column(Integer, default=0, server_default="0", nullable=False)               # 0 | 50 | 70

    # RBAC governance role (super_admin, security_auditor, engineering_lead,
    # compliance_officer, viewer); NULL for candidates and employers.
    role                = Column(String, nullable=True, index=True)
    # Incremented on password reset / "log out everywhere": invalidates JWTs.
    token_version       = Column(Integer, default=0, nullable=False, server_default="0")

    # ── Account integrity & security controls ────────────────────────────────
    # Normalised address (lower-case, +tag removed, Gmail dots removed) used to
    # reject duplicate sign-ups such as j.doe+2@gmail.com vs jdoe@gmail.com.
    email_canonical      = Column(String(255), nullable=True, index=True)
    signup_ip            = Column(String(64), nullable=True)
    suspended_at         = Column(DateTime, nullable=True)
    suspended_reason     = Column(String(255), nullable=True)
    force_password_reset = Column(Boolean, default=False, nullable=False, server_default="false")
    last_login_at        = Column(DateTime, nullable=True)
    last_login_ip        = Column(String(64), nullable=True)
    last_login_location  = Column(String(128), nullable=True)
    # Two-step verification (TOTP). The secret is encrypted at rest; recovery
    # codes are stored as SHA-256 hashes and consumed on use.
    totp_secret          = Column(String(255), nullable=True)
    totp_enabled_at      = Column(DateTime, nullable=True)
    totp_recovery_codes  = Column(JSON, nullable=True)
    # Employer review
    company_url          = Column(String(255), nullable=True)
    hr_job_title         = Column(String(128), nullable=True)
    hr_rejected_at       = Column(DateTime, nullable=True)
    hr_rejected_reason   = Column(String(255), nullable=True)

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


class ProfilePhoto(Base):
    """Profile picture stored in the database so it survives redeploys.

    Always a re-encoded 512x512 image (metadata stripped). ``token`` changes on
    every upload, so the public URL can be cached forever."""
    __tablename__ = "profile_photos"
    user_id      = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    token        = Column(String(32), unique=True, nullable=False)
    content      = Column(LargeBinary, nullable=False)
    content_type = Column(String(32), nullable=False, default="image/webp")
    updated_at   = Column(DateTime, default=datetime.utcnow, nullable=False)
