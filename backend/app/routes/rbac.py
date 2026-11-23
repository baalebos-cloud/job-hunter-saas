"""RBAC administration: policy matrix and governance-role assignment."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.dependencies.roles import (LOCKED_PERMISSIONS, PERMISSIONS, ROLES, ensure_rbac_seed,
                                            policy_matrix, require_permission)
from backend.app.models.user import User

router = APIRouter(tags=["RBAC"])


class RoleAssignment(BaseModel):
    role: Optional[str] = Field(default=None, description="Governance role, or null to remove it")


class RolePermissions(BaseModel):
    permissions: list[str] = Field(max_length=len(PERMISSIONS))


def _audit(request_state, action, **details):
    try:
        from backend.app.services.audit import record_event
        record_event(action=action, actor=getattr(request_state, 'user', None), details=details)
    except Exception:
        pass


@router.get("/matrix")
def get_matrix(db: Session = Depends(get_db), _=Depends(require_permission('users:read'))):
    return {"roles": policy_matrix(db), "permissions": PERMISSIONS}


@router.get("/users")
def list_role_holders(db: Session = Depends(get_db), _=Depends(require_permission('users:read')),
                      q: str = '', limit: int = 50):
    query = db.query(User.id, User.email, User.full_name, User.role, User.is_verified, User.career_track,
                     User.totp_enabled_at, User.created_at, User.last_login_at, User.is_hr)
    if q:
        query = query.filter(User.email.ilike(f'%{q.strip()}%'))
    else:
        query = query.filter(User.role.isnot(None))
    rows = query.order_by(User.email).limit(min(max(limit, 1), 200)).all()
    # Profile details shown before a role is assigned (Owner console -> Access control).
    return [{"id": r.id, "email": r.email, "full_name": r.full_name, "role": r.role, "is_verified": r.is_verified,
             "career_track": r.career_track, "two_step": bool(r.totp_enabled_at), "is_employer": bool(r.is_hr),
             "joined": r.created_at.isoformat() + 'Z' if r.created_at else None,
             "last_login": r.last_login_at.isoformat() + 'Z' if r.last_login_at else None}
            for r in rows]


@router.put("/users/{user_id}/role")
def assign_role(user_id: int, body: RoleAssignment, request: Request, db: Session = Depends(get_db),
                actor=Depends(require_permission('users:manage_roles'))):
    if body.role is not None and body.role not in ROLES:
        raise HTTPException(422, f"Unknown role. Choose one of: {', '.join(ROLES)}.")
    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    if not user:
        raise HTTPException(404, "User not found")
    if body.role and not user.is_verified:
        raise HTTPException(400, "Verify the account email before granting a governance role.")
    if user.role == 'super_admin' and body.role != 'super_admin':
        remaining = db.query(User).filter(User.role == 'super_admin', User.id != user.id, User.is_verified.is_(True)).count()
        if remaining == 0:
            raise HTTPException(409, "At least one verified super_admin must remain.")
    previous = user.role
    user.role = body.role
    user.is_admin = body.role == 'super_admin'  # legacy flag kept in sync for reporting
    # Role changes take effect immediately: invalidate existing access tokens.
    from backend.app.services.auth_service import revoke_all_sessions
    revoke_all_sessions(db, user)
    db.commit()
    _audit(None, 'rbac.role_assigned', target_user_id=user.id, previous=previous, role=body.role, actor_id=actor.id)
    from backend.app.services import security_events
    security_events.record('admin.made_admin' if body.role == 'super_admin' else 'admin.role_changed', request, user=actor,
                           details={'target_user_id': user.id, 'target_email': user.email, 'previous': previous, 'role': body.role})
    return {"id": user.id, "email": user.email, "role": user.role}


@router.put("/roles/{role}/permissions")
def set_role_permissions(role: str, body: RolePermissions, db: Session = Depends(get_db),
                         actor=Depends(require_permission('users:manage_roles'))):
    from backend.app.models.security import RbacPermission
    ensure_rbac_seed(db)
    if role not in ROLES:
        raise HTTPException(404, "Unknown role")
    unknown = sorted(set(body.permissions) - set(PERMISSIONS))
    if unknown:
        raise HTTPException(422, f"Unknown permissions: {', '.join(unknown)}")
    missing_locked = LOCKED_PERMISSIONS.get(role, set()) - set(body.permissions)
    if missing_locked:
        raise HTTPException(409, f"{role} must keep: {', '.join(sorted(missing_locked))}")
    db.query(RbacPermission).filter(RbacPermission.role == role).delete(synchronize_session=False)
    for permission in sorted(set(body.permissions)):
        db.add(RbacPermission(role=role, permission=permission))
    db.commit()
    _audit(None, 'rbac.matrix_updated', role=role, permissions=sorted(set(body.permissions)), actor_id=actor.id)
    return {"role": role, "permissions": sorted(set(body.permissions))}
