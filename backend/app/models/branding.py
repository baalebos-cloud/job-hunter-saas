"""Custom branding for Enterprise exports: a brand name, a logo and an accent
colour shown in the header and footer of branded PDF and Word downloads.

One row per Enterprise account owner. Members of the owner's team use the
owner's branding; only the owner can change it.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, LargeBinary, String

from backend.app.database import Base

DEFAULT_ACCENT = '#059669'


class Branding(Base):
    __tablename__ = 'brandings'

    owner_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    brand_name = Column(String(60), nullable=True)
    accent_color = Column(String(7), nullable=False, default=DEFAULT_ACCENT)
    logo = Column(LargeBinary, nullable=True)          # PNG, re-encoded and resized on upload
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @property
    def configured(self) -> bool:
        return bool(self.brand_name or self.logo)
