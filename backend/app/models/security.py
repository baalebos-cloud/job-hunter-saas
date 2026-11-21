"""Refresh-token sessions and the database-backed RBAC policy matrix."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, Index

from backend.app.database import Base


class RefreshToken(Base):
    """One row per issued refresh token. Only a SHA-256 hash is stored.

    Tokens rotate on every use; presenting an already-rotated token revokes the
    whole family (theft detection)."""
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False)
    family_id = Column(String(36), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    replaced_by_id = Column(Integer, nullable=True)


class RbacRole(Base):
    __tablename__ = "rbac_roles"

    name = Column(String(64), primary_key=True)
    description = Column(String(255), nullable=False, default="")
    is_system = Column(Boolean, nullable=False, default=True)


class RbacPermission(Base):
    __tablename__ = "rbac_role_permissions"
    __table_args__ = (UniqueConstraint("role", "permission", name="uq_rbac_role_permission"),
                      Index("ix_rbac_role_permissions_role", "role"))

    id = Column(Integer, primary_key=True)
    role = Column(String(64), ForeignKey("rbac_roles.name", ondelete="CASCADE"), nullable=False)
    permission = Column(String(64), nullable=False)


class BlockedIP(Base):
    """IP addresses refused at sign-in and sign-up. ``expires_at`` NULL = permanent."""
    __tablename__ = "blocked_ips"

    id = Column(Integer, primary_key=True)
    ip = Column(String(64), unique=True, nullable=False)
    reason = Column(String(255), nullable=True)
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)


class DismissedDuplicate(Base):
    """A suspected-duplicate group an admin reviewed and marked as legitimate."""
    __tablename__ = "dismissed_duplicates"

    id = Column(Integer, primary_key=True)
    group_key = Column(String(160), unique=True, nullable=False)
    dismissed_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
