"""Append-only audit trail and GDPR erasure tombstones.

``audit_logs`` holds no raw PII: actors are recorded as a keyed hash plus a
redacted email, IPs are masked, query strings are never stored. On
PostgreSQL a trigger rejects UPDATE/DELETE except for the retention job.
"""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, Column, DateTime, Float, Index, Integer, String

from backend.app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_ts", "ts"), Index("ix_audit_logs_actor_ts", "actor_hash", "ts"),
                      Index("ix_audit_logs_action_ts", "action", "ts"))

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    ts = Column(DateTime, nullable=False, default=datetime.utcnow)
    trace_id = Column(String(32), nullable=False)
    kind = Column(String(16), nullable=False, default="request")  # request | event
    action = Column(String(64), nullable=False)                    # e.g. http.request, rbac.role_assigned
    actor_hash = Column(String(24), nullable=True)
    actor_display = Column(String(120), nullable=True)            # redacted, e.g. j***@g***.com
    actor_role = Column(String(32), nullable=True)
    method = Column(String(8), nullable=True)
    route = Column(String(200), nullable=True)                    # route template, never the query string
    status = Column(Integer, nullable=True)
    latency_ms = Column(Float, nullable=True)
    outcome = Column(String(16), nullable=True)                   # success | denied | client_error | error
    ip_masked = Column(String(64), nullable=True)
    details = Column(JSON, nullable=True)


class ErasureTombstone(Base):
    """Proof of an Art. 17 erasure, without personal data, plus any object
    deletions that still need to be retried."""
    __tablename__ = "erasure_tombstones"

    id = Column(Integer, primary_key=True)
    subject_hash = Column(String(24), nullable=False, index=True)
    erased_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    requested_by = Column(String(16), nullable=False, default="self")
    deleted_counts = Column(JSON, nullable=True)
    pending_object_keys = Column(JSON, nullable=True)
    completed_at = Column(DateTime, nullable=True)
