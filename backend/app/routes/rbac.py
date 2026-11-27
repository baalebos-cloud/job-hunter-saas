"""RBAC administration: policy matrix and governance-role assignment."""
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
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
def assign_role(user_id: int, body: RoleAssignment, request: Request, background: BackgroundTasks,
                db: Session = Depends(get_db), actor=Depends(require_permission('users:manage_roles'))):
    """Offer a staff role (an emailed invitation the person must accept) or remove one.

    Removing a role takes effect immediately; granting one waits for acceptance."""
    from backend.app.services import security_events, staff_invitations
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
    if body.role is not None and body.role != previous:
        invite, raw = staff_invitations.create(db, user, body.role, actor)
        db.commit()
        _audit(None, 'rbac.role_invited', target_user_id=user.id, role=body.role, actor_id=actor.id)
        security_events.record('admin.role_invited', request, user=actor,
                               details={'target_user_id': user.id, 'target_email': user.email, 'role': body.role})
        background.add_task(staff_invitations.send, user.email, user.full_name, body.role, actor.full_name or None, raw)
        return {"id": user.id, "email": user.email, "role": previous, "status": "invited", "invited_role": body.role,
                "invitation_id": invite.id, "expires_at": invite.expires_at.isoformat() + 'Z', "notified": True}
    cancelled = staff_invitations.cancel_pending(db, user.id)
    if body.role == previous:
        db.commit()
        return {"id": user.id, "email": user.email, "role": user.role, "status": "unchanged", "notified": False,
                "cancelled_invitations": cancelled}
    # Removal: effective immediately, signed out everywhere.
    user.role, user.is_admin = None, False
    from backend.app.services.auth_service import revoke_all_sessions
    revoke_all_sessions(db, user)
    db.commit()
    _audit(None, 'rbac.role_assigned', target_user_id=user.id, previous=previous, role=None, actor_id=actor.id)
    security_events.record('admin.role_changed', request, user=actor,
                           details={'target_user_id': user.id, 'target_email': user.email, 'previous': previous, 'role': None})
    from backend.app.services.role_emails import send_role_change
    background.add_task(send_role_change, user, previous, None, actor.full_name or None)
    return {"id": user.id, "email": user.email, "role": None, "status": "removed", "notified": True}


def _invitation_row(db, invite) -> dict:
    from backend.app.services.staff_invitations import state
    person = db.get(User, invite.user_id)
    inviter = db.get(User, invite.invited_by) if invite.invited_by else None
    return {"id": invite.id, "user_id": invite.user_id, "email": person.email if person else None,
            "full_name": person.full_name if person else None, "role": invite.role, "status": state(invite),
            "invited_by": (inviter.full_name or inviter.email) if inviter else None,
            "created_at": invite.created_at.isoformat() + 'Z', "expires_at": invite.expires_at.isoformat() + 'Z'}


@router.get("/invitations")
def list_invitations(db: Session = Depends(get_db), _=Depends(require_permission('users:read'))):
    """Invitations still waiting for an answer (including ones that expired unanswered)."""
    from backend.app.models.security import StaffInvitation
    rows = db.query(StaffInvitation).filter(StaffInvitation.status == 'pending').order_by(StaffInvitation.id.desc()).all()
    return [_invitation_row(db, r) for r in rows]


def _pending_invite(db, invitation_id: int):
    from backend.app.models.security import StaffInvitation
    invite = db.get(StaffInvitation, invitation_id)
    if not invite or invite.status != 'pending':
        raise HTTPException(404, "No pending invitation with that id.")
    return invite


@router.post("/invitations/{invitation_id}/resend")
def resend_invitation(invitation_id: int, request: Request, background: BackgroundTasks, db: Session = Depends(get_db),
                      actor=Depends(require_permission('users:manage_roles'))):
    """A fresh link (the old one stops working) valid for another 7 days."""
    from backend.app.services import security_events, staff_invitations
    invite = _pending_invite(db, invitation_id)
    person = db.get(User, invite.user_id)
    raw = staff_invitations.refresh_token(db, invite)
    db.commit()
    security_events.record('admin.role_invited', request, user=actor,
                           details={'target_user_id': person.id, 'target_email': person.email, 'role': invite.role, 'resent': True})
    background.add_task(staff_invitations.send, person.email, person.full_name, invite.role, actor.full_name or None, raw)
    return _invitation_row(db, invite)


@router.delete("/invitations/{invitation_id}")
def cancel_invitation(invitation_id: int, request: Request, db: Session = Depends(get_db),
                      actor=Depends(require_permission('users:manage_roles'))):
    from datetime import datetime
    from backend.app.services import security_events
    invite = _pending_invite(db, invitation_id)
    invite.status, invite.responded_at = 'cancelled', datetime.utcnow()
    db.commit()
    security_events.record('admin.role_invite_cancelled', request, user=actor,
                           details={'target_user_id': invite.user_id, 'role': invite.role})
    return {"message": "Invitation cancelled"}


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
