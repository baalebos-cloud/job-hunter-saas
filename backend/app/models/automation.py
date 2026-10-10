"""Persistent notification attempts and scraper heartbeats."""
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String
from backend.app.database import Base


class AutomationEvent(Base):
    __tablename__ = "automation_events"

    event_id = Column(String(160), primary_key=True)
    event_type = Column(String(40), nullable=False)
    recipient_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    payload = Column(JSON, nullable=False)
    status = Column(String(20), nullable=False, default="pending", index=True)
    attempts = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    next_attempt_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    first_attempt_at = Column(DateTime, nullable=True)
    locked_until = Column(DateTime, nullable=True)
    lease_token = Column(String(32), nullable=True)
    sent_at = Column(DateTime, nullable=True)
    last_error = Column(String(80), nullable=True)


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id = Column(String(32), primary_key=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="running")
    summary = Column(JSON, nullable=False, default=dict)


class AutomationState(Base):
    __tablename__ = "automation_state"

    key = Column(String(80), primary_key=True)
    value = Column(JSON, nullable=False)
