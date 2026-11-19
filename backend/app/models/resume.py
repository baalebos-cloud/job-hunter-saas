from datetime import datetime

from sqlalchemy import Index, Column, DateTime, Float, ForeignKey, Integer, JSON, LargeBinary, String, Text
from sqlalchemy.orm import relationship

from backend.app.database import Base


class Resume(Base):
    __tablename__ = "resumes"
    __table_args__ = (Index("uq_resumes_owner_filename", "owner_id", "filename", unique=True),)

    id = Column(Integer, primary_key=True, index=True)

    # FK linking to the User table
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    filename = Column(String, nullable=False)
    # PDFs live in private, KMS-encrypted object storage (storage_key) when it
    # is configured. ``content`` is the transitional/dev fallback only and is
    # NULL for objects in S3 (expand/contract: dropped after the backfill).
    content = Column(LargeBinary, nullable=True)
    storage_key = Column(String(512), nullable=True)
    sha256 = Column(String(64), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    # processing | completed | failed (async refiner jobs)
    status = Column(String(16), nullable=False, default="completed", server_default="completed")
    error = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)
    parsed_data = Column(Text, nullable=True)
    ats_score = Column(Float, default=0.0)
    analysis_data = Column(JSON, nullable=True)

    # This name 'owner' MUST match the 'back_populates' in user.py
    owner = relationship("User", back_populates="resumes")
