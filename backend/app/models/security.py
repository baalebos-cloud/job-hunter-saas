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


class SignupRule(Base):
    """Owner-managed sign-up rules: an extra blocked email domain, or a trusted
    network (office, school) where several people may create accounts."""
    __tablename__ = "signup_rules"
    __table_args__ = (UniqueConstraint("kind", "value", name="uq_signup_rule"),)

    id = Column(Integer, primary_key=True)
    kind = Column(String(20), nullable=False)          # blocked_domain | allowed_network
    value = Column(String(255), nullable=False)        # domain, or IP / CIDR
    note = Column(String(255), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
class StaffInvitation(Base):
    """A staff role offered to an existing account. The role is granted only when
    the person accepts through the emailed link (single use, expires); only a
    SHA-256 hash of the link token is stored."""
    __tablename__ = "staff_invitations"
    __table_args__ = (Index("ix_staff_invitations_user_status", "user_id", "status"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(64), nullable=False)
    token_hash = Column(String(64), unique=True, nullable=False)
    status = Column(String(16), nullable=False, default="pending")   # pending|accepted|declined|cancelled
    invited_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    responded_at = Column(DateTime, nullable=True)
    confidentiality_agreed = Column(Boolean, nullable=False, default=False)
