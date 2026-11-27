"""Legal documents (Terms, Privacy, Cookies, Refunds, Acceptable Use).

Every publish is a new numbered version, kept for the record; at most one
working draft per document. Until a version is published the site shows the
bundled starter text, marked as a draft pending legal review."""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text

from backend.app.database import Base


class LegalDocumentVersion(Base):
    __tablename__ = "legal_document_versions"
    __table_args__ = (Index("ix_legal_versions_slug_status", "slug", "status"),)

    id = Column(Integer, primary_key=True)
    slug = Column(String(40), nullable=False)
    version = Column(Integer, nullable=True)            # set when published
    status = Column(String(12), nullable=False)          # draft | published
    title = Column(String(120), nullable=False)
    body = Column(Text, nullable=False)
    note = Column(String(255), nullable=True)            # what changed, shown in the history
    edited_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    published_at = Column(DateTime, nullable=True)
