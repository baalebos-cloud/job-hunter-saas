"""The Resume Studio document a person edits by hand (one per person)."""
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String

from backend.app.database import Base


class StudioDocument(Base):
    __tablename__ = "studio_documents"
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    data       = Column(JSON, nullable=False)                 # ResumeData (see services/studio.py)
    paper      = Column(String(8), nullable=False, default="A4")
    preset     = Column(String(32), nullable=False, default="as-is")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
