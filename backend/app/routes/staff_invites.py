"""The invited person's side of a staff role invitation (/staff-invite page)."""
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.dependencies.auth import get_current_user
from backend.app.models.user import User

router = APIRouter(tags=["Staff invitations"])


class InviteToken(BaseModel):
    token: str
    confidentiality: bool = False


def _open(db, token: str):
    from backend.app.services.staff_invitations import find, state
    invite = find(db, token)
    if invite is None:
        raise HTTPException(404, "This invitation link is not valid. Ask the Baalebos owner to send a new one.")
    current = state(invite)
    if current != 'pending':
        messages = {'expired': 'This invitation has expired. Ask the Baalebos owner to send a new one.',
                    'accepted': 'This invitation was already accepted.',
                    'declined': 'This invitation was declined.',
                    'cancelled': 'This invitation was withdrawn by the Baalebos owner.'}
        raise HTTPException(410, messages.get(current, 'This invitation is no longer valid.'))
    return invite


@router.get("/{token}")
def invitation_details(token: str, db: Session = Depends(get_db)):
    """What the link offers. The token is the secret; the invited address is shown masked."""
    from backend.app.services.role_emails import ROLE_GUIDE
    from backend.app.services.staff_invitations import mask_email
    invite = _open(db, token)
    person = db.get(User, invite.user_id)
    inviter = db.get(User, invite.invited_by) if invite.invited_by else None
    guide = ROLE_GUIDE.get(invite.role, {'label': invite.role, 'summary': '', 'can': [], 'place': 'the console', 'where': '/admin'})
    return {"role": invite.role, "label": guide['label'], "summary": guide['summary'], "can": guide['can'],
            "place": guide.get('place'), "where": guide.get('where'),
            "invited_email": mask_email(person.email if person else ''),
            "invited_by": (inviter.full_name or 'The Baalebos owner') if inviter else 'The Baalebos owner',
            "created_at": invite.created_at.isoformat() + 'Z', "expires_at": invite.expires_at.isoformat() + 'Z'}


@router.post("/accept")
def accept(body: InviteToken, request: Request, background: BackgroundTasks, db: Session = Depends(get_db),
           current_user=Depends(get_current_user)):
    from backend.app.services import security_events
    from backend.app.services.auth_service import revoke_all_sessions
    from backend.app.services.staff_invitations import mask_email
    invite = _open(db, body.token)
    if invite.user_id != current_user.id:
        person = db.get(User, invite.user_id)
        raise HTTPException(403, f"This invitation is for {mask_email(person.email if person else '')}. "
                                 "Sign out, then sign in to that account to accept it.")
    if not body.confidentiality:
        raise HTTPException(422, "Agree to keep user data confidential to accept the role.")
    user = db.query(User).filter(User.id == current_user.id).with_for_update().first()
    previous = user.role
    user.role, user.is_admin = invite.role, invite.role == 'super_admin'
    invite.status, invite.responded_at, invite.confidentiality_agreed = 'accepted', datetime.utcnow(), True
    revoke_all_sessions(db, user)          # new access starts with a fresh sign-in (and two-step setup)
    db.commit()
    try:
        from backend.app.services.audit import record_event
        record_event(action='rbac.role_assigned', actor=None,
                     details={'target_user_id': user.id, 'previous': previous, 'role': invite.role, 'via': 'invitation'})
    except Exception:
        pass
    security_events.record('staff.invite_accepted', request, user=user, details={'role': invite.role, 'previous': previous})
    inviter = db.get(User, invite.invited_by) if invite.invited_by else None
    from backend.app.services.role_emails import send_role_change
    background.add_task(send_role_change, user, previous, invite.role, (inviter.full_name if inviter else None))
    return {"role": invite.role, "status": "accepted", "sign_in_again": True,
            "two_step_required": not bool(user.totp_enabled_at)}


@router.post("/decline")
def decline(body: InviteToken, request: Request, db: Session = Depends(get_db)):
    """Declining needs only the link: nothing is granted, so no sign-in is required."""
    from backend.app.services import security_events
    invite = _open(db, body.token)
    invite.status, invite.responded_at = 'declined', datetime.utcnow()
    db.commit()
    person = db.get(User, invite.user_id)
    security_events.record('staff.invite_declined', request, user=person, details={'role': invite.role})
    return {"status": "declined"}
