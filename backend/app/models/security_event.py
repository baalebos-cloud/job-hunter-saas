"""Security events for owner oversight: sign-ins, sign-ups, resets and admin actions.

Unlike the general audit trail (masked IPs, hashed actors), these rows keep the
full client IP, coarse location and the account involved, because the owner
needs them to investigate abuse. They are purpose-limited: written only for
security-relevant events, readable only by admins, included in the user's data
export, deleted on erasure and purged after SECURITY_EVENT_RETENTION_DAYS.
"""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, Column, DateTime, Index, Integer, String

from backend.app.database import Base


class SecurityEvent(Base):
    __tablename__ = "security_events"
    __table_args__ = (
        Index("ix_security_events_ts", "ts"),
        Index("ix_security_events_event_ts", "event", "ts"),
        Index("ix_security_events_ip_ts", "ip", "ts"),
        Index("ix_security_events_user_id", "user_id"),
    )

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    ts = Column(DateTime, nullable=False, default=datetime.utcnow)
    event = Column(String(40), nullable=False)        # e.g. login.success, login.failed, admin.hr_approved
    portal = Column(String(16), nullable=True)        # login | hr | admin
    user_id = Column(Integer, nullable=True)          # no FK: the trail survives account deletion until retention/erasure
    email = Column(String(255), nullable=True)
    ip = Column(String(64), nullable=True)
    country_code = Column(String(2), nullable=True)
    country = Column(String(64), nullable=True)
    region = Column(String(64), nullable=True)
    city = Column(String(64), nullable=True)
    user_agent = Column(String(255), nullable=True)
    details = Column(JSON, nullable=True)
