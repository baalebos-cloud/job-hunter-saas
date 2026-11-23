"""API keys for the Enterprise integrations API.

The full key is shown once, when it is created. Only its SHA-256 hash and a
short prefix (to recognise it in the list) are stored. Revoked keys stop
working immediately and are kept for the audit trail.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from backend.app.database import Base

MAX_ACTIVE_KEYS = 5
RATE_LIMIT_PER_MINUTE = 60
KEY_PREFIX = 'bb_live_'


class ApiKey(Base):
    __tablename__ = 'api_keys'

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    name = Column(String(60), nullable=False)
    prefix = Column(String(16), nullable=False)               # e.g. "bb_live_AbC1" to recognise the key
    key_hash = Column(String(64), nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
