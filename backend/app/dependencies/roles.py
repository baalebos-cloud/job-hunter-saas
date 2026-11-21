"""Database-backed RBAC.

Governance roles and their permissions live in ``rbac_roles`` /
``rbac_role_permissions`` (seeded from ``DEFAULT_MATRIX`` by the migration
and on first use). A user's role is ``users.role``. Candidate and employer
access (``require_hr``) is unchanged: it depends on the approved-HR flags,
not on governance roles.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.dependencies.auth import get_current_user

PERMISSIONS = {
    'admin:access': 'Owner console: platform stats, users, jobs, automation',
    'users:read': 'View user accounts and roles',
    'users:manage_roles': 'Assign governance roles and edit the policy matrix',
    'audit:read': 'View the audit trail',
    'audit:export': 'Export audit records and compliance reports',
    'metrics:read': 'View service metrics and alerts',
    'reports:read': 'Download weekly analytical reports',
    'privacy:manage': 'Handle data-subject requests (export / erasure)',
    'system:diagnostics': 'Run provider and infrastructure diagnostics',
    'jobs:manage': 'Moderate job listings and approve employers',
}

DEFAULT_MATRIX = {
    'super_admin': ('Full platform administration', sorted(PERMISSIONS)),
    'security_auditor': ('Read-only security and audit review',
                         ['audit:read', 'audit:export', 'metrics:read', 'reports:read', 'users:read']),
    'engineering_lead': ('Operational health and diagnostics',
                         ['metrics:read', 'reports:read', 'system:diagnostics', 'jobs:manage']),
    'compliance_officer': ('GDPR/SOC2 evidence and data-subject requests',
                           ['audit:read', 'audit:export', 'reports:read', 'privacy:manage', 'users:read']),
    'viewer': ('Read-only dashboards', ['metrics:read', 'reports:read']),
}
ROLES = tuple(DEFAULT_MATRIX)
# super_admin must always be able to administer roles (no lock-out).
LOCKED_PERMISSIONS = {'super_admin': {'admin:access', 'users:manage_roles'}}


def ensure_rbac_seed(db: Session) -> None:
    """Insert the default matrix when the policy tables are empty."""
    from backend.app.models.security import RbacPermission, RbacRole
    if db.query(RbacRole).count():
        return
    for role, (description, permissions) in DEFAULT_MATRIX.items():
        db.add(RbacRole(name=role, description=description, is_system=True))
        db.flush()
        for permission in permissions:
            db.add(RbacPermission(role=role, permission=permission))
    db.commit()


def role_permissions(db: Session, role: str | None) -> set[str]:
    from backend.app.models.security import RbacPermission
    if not role:
        return set()
    ensure_rbac_seed(db)
    return {p for (p,) in db.query(RbacPermission.permission).filter(RbacPermission.role == role).all()}


def policy_matrix(db: Session) -> dict:
    from backend.app.models.security import RbacPermission, RbacRole
    ensure_rbac_seed(db)
    matrix = {r.name: {'description': r.description, 'permissions': []} for r in db.query(RbacRole).order_by(RbacRole.name)}
    for permission in db.query(RbacPermission).order_by(RbacPermission.permission):
        matrix.setdefault(permission.role, {'description': '', 'permissions': []})['permissions'].append(permission.permission)
    return matrix


def has_permission(db: Session, user, permission: str) -> bool:
    return bool(user and user.is_verified and permission in role_permissions(db, user.role))


def require_permission(permission: str):
    if permission not in PERMISSIONS:
        raise ValueError(f'Unknown permission {permission}')

    def dependency(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
        if not has_permission(db, current_user, permission):
            _forbidden(permission)
        return current_user
    dependency.__name__ = f'require_{permission.replace(":", "_")}'
    return dependency


def _forbidden(permission: str):
    try:
        from backend.app.core.metrics import UNAUTHORIZED_ATTEMPTS
        UNAUTHORIZED_ATTEMPTS.labels(status='403', reason=permission).inc()
    except Exception:
        pass
    raise HTTPException(403, 'You do not have permission to perform this action.')


def is_owner(user) -> bool:
    """Platform administrator (super_admin). Kept for existing call sites."""
    return bool(user and user.is_verified and getattr(user, 'role', None) == 'super_admin')


_require_admin_access = require_permission('admin:access')


def require_admin(current_user=Depends(_require_admin_access)):
    """Owner console access. With ADMIN_2FA_REQUIRED (default on) the account
    must have two-step verification enabled; sign-in already demanded the code."""
    from backend.app.services.mfa import admin_2fa_required
    if admin_2fa_required() and not current_user.totp_enabled_at:
        raise HTTPException(403, {'code': 'mfa_enrollment_required',
                                  'message': 'Turn on two-step verification to use the Owner console.'})
    return current_user


def require_hr(current_user=Depends(get_current_user)):
    if not is_owner(current_user) and not (current_user.is_hr and current_user.is_verified and current_user.hr_approved):
        raise HTTPException(403, "Approved HR access required.")
    return current_user
