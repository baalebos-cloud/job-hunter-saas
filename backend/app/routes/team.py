"""Enterprise team access.

The Enterprise owner invites up to 9 people by email (10 seats including the
owner). An invite is a single-use link that expires after 7 days and can only
be accepted by someone signed in with the invited email address. Members get
Enterprise for as long as the owner's plan is active. Each person's resumes,
applications and profile stay private to them: the team shares the plan only.
"""
import re
from datetime import datetime, timedelta
from html import escape

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.database import get_db
from backend.app.dependencies.auth import get_current_user
from backend.app.dependencies.plan_guard import own_plan, team_owner
from backend.app.models.team import INVITE_DAYS, TEAM_SEATS, TeamMember
from backend.app.models.user import User
from backend.app.services.account_integrity import canonical_email
from backend.app.services.audit import record_event
from backend.app.services.auth_service import hash_token, new_opaque_token

router = APIRouter(tags=['Team'])

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


class InviteBody(BaseModel):
    email: str = Field(..., max_length=255)


class TokenBody(BaseModel):
    token: str = Field(..., min_length=10, max_length=200)


def _name(user: User) -> str:
    return user.full_name or user.email.split('@')[0]


def _limit(key: str, limit: int, window: int):
    from backend.app.core.rate_limit import hit
    allowed, retry = hit(key, limit, window)
    if not allowed:
        raise HTTPException(429, 'Too many team changes in a short time. Please wait a few minutes and try again.',
                            headers={'Retry-After': str(retry)})


def _serialize(row: TeamMember, db: Session) -> dict:
    member = db.get(User, row.user_id) if row.user_id else None
    return {'id': row.id, 'email': row.email, 'name': (member.full_name if member else None),
            'status': 'expired' if row.expired else row.status,
            'invited_at': row.invited_at.isoformat() if row.invited_at else None,
            'expires_at': row.expires_at.isoformat() if row.expires_at and row.status == 'invited' else None,
            'accepted_at': row.accepted_at.isoformat() if row.accepted_at else None}


def _require_owner(db: Session, user: User):
    if own_plan(db, user) != 'enterprise':
        raise HTTPException(403, {'error': 'enterprise_required',
                                  'message': 'Team access is part of the Enterprise plan.', 'upgrade_url': '/pricing'})


def _seats_taken(db: Session, owner_id: int) -> int:
    rows = db.query(TeamMember).filter(TeamMember.owner_id == owner_id).all()
    return 1 + sum(1 for r in rows if not r.expired)        # the owner holds one seat


def _send_invite(owner: User, row: TeamMember, raw_token: str):
    from backend.app.utils import email
    link = f"{settings.FRONTEND_URL.rstrip('/')}/team/join?token={raw_token}"
    who = escape(_name(owner))
    html = f"""<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;background:#f8fafc;padding:32px 16px;color:#0f172a">
<div style="max-width:560px;margin:0 auto;background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:28px">
<p style="font-size:13px;color:#059669;font-weight:bold;margin:0 0 8px">Baalebos</p>
<h1 style="font-size:20px;margin:0 0 12px">{who} invited you to their Enterprise team</h1>
<p style="font-size:14px;line-height:1.6;margin:0 0 12px">Join the team to use Baalebos Enterprise at no cost to you while
{who}'s plan is active: unlimited resume tailoring, priority processing, tailoring for up to 10 jobs at once
and your last 30 tailored resumes.</p>
<p style="font-size:14px;line-height:1.6;margin:0 0 20px">Your resumes, applications and profile stay private to you.
The team shares the plan only.</p>
<p style="margin:0 0 20px"><a href="{escape(link)}" style="background:#059669;color:#fff;text-decoration:none;font-weight:bold;
padding:12px 20px;border-radius:10px;display:inline-block">Accept the invite</a></p>
<p style="font-size:12px;color:#64748b;line-height:1.6;margin:0">Sign in (or create an account) with
<strong>{escape(row.email)}</strong> to accept. This link works once and expires in {INVITE_DAYS} days.
If you were not expecting this, you can ignore this email.</p>
</div><p style="text-align:center;font-size:11px;color:#94a3b8">Baalebos · {escape(settings.SUPPORT_EMAIL)}</p>
</body></html>"""
    email.send_account_message(row.email, f'{_name(owner)} invited you to their Baalebos Enterprise team', html,
                               reply_to=owner.email)


def _issue(row: TeamMember) -> str:
    raw, digest = new_opaque_token()
    row.token_hash = digest
    now = datetime.utcnow()
    row.invited_at = now
    row.expires_at = now + timedelta(days=INVITE_DAYS)
    return raw


@router.get('')
def my_team(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    membership = db.query(TeamMember).filter(TeamMember.user_id == current_user.id,
                                             TeamMember.status == 'active').first()
    if membership:
        owner = db.get(User, membership.owner_id)
        return {'role': 'member', 'seats_total': TEAM_SEATS, 'active': team_owner(db, current_user) is not None,
                'owner': {'name': _name(owner), 'email': owner.email} if owner else None,
                'joined_at': membership.accepted_at.isoformat() if membership.accepted_at else None}
    rows = (db.query(TeamMember).filter(TeamMember.owner_id == current_user.id)
            .order_by(TeamMember.status, TeamMember.invited_at).all())
    can_manage = own_plan(db, current_user) == 'enterprise'
    return {'role': 'owner' if (rows or can_manage) else 'none', 'can_manage': can_manage,
            'seats_total': TEAM_SEATS, 'seats_used': _seats_taken(db, current_user.id),
            'members': [_serialize(r, db) for r in rows]}


@router.post('/invites', status_code=201)
def invite(body: InviteBody, background: BackgroundTasks, request: Request, db: Session = Depends(get_db),
           current_user: User = Depends(get_current_user)):
    _require_owner(db, current_user)
    if db.query(TeamMember).filter(TeamMember.user_id == current_user.id, TeamMember.status == 'active').first():
        raise HTTPException(409, 'You are a member of another team. Leave it before inviting people to your own.')
    address = body.email.strip()
    if not EMAIL_RE.match(address):
        raise HTTPException(400, 'Enter a valid email address.')
    canon = canonical_email(address)
    if canon == canonical_email(current_user.email):
        raise HTTPException(400, 'You are already on your team as its owner.')
    existing = db.query(TeamMember).filter(TeamMember.owner_id == current_user.id,
                                           TeamMember.email_canonical == canon).first()
    if existing and not existing.expired:
        raise HTTPException(409, 'This person is already on your team or has a pending invite.')
    if not existing and _seats_taken(db, current_user.id) >= TEAM_SEATS:
        raise HTTPException(400, f'Your team is full ({TEAM_SEATS} seats including you). '
                                 'Remove someone or cancel an invite to free a seat.')
    _limit(f'team-invite:{current_user.id}', 30, 3600)
    row = existing or TeamMember(owner_id=current_user.id, email=address.lower(), email_canonical=canon)
    raw = _issue(row)
    db.add(row)
    db.commit()
    background.add_task(_send_invite, current_user, row, raw)
    record_event('team.invite', actor=current_user, trace_id=getattr(request.state, 'trace_id', None),
                 details={'member_id': row.id})
    return _serialize(row, db)


@router.post('/invites/{member_id}/resend')
def resend(member_id: int, background: BackgroundTasks, db: Session = Depends(get_db),
           current_user: User = Depends(get_current_user)):
    _require_owner(db, current_user)
    row = db.query(TeamMember).filter(TeamMember.id == member_id, TeamMember.owner_id == current_user.id).first()
    if not row:
        raise HTTPException(404, 'Invite not found.')
    if row.status != 'invited':
        raise HTTPException(409, 'This person has already joined your team.')
    _limit(f'team-invite:{current_user.id}', 30, 3600)
    raw = _issue(row)
    db.commit()
    background.add_task(_send_invite, current_user, row, raw)
    return _serialize(row, db)


@router.delete('/members/{member_id}')
def remove(member_id: int, request: Request, db: Session = Depends(get_db),
           current_user: User = Depends(get_current_user)):
    """Remove a member or cancel an invite. The member keeps their account and resumes."""
    row = db.query(TeamMember).filter(TeamMember.id == member_id, TeamMember.owner_id == current_user.id).first()
    if not row:
        raise HTTPException(404, 'Team member not found.')
    db.delete(row)
    db.commit()
    record_event('team.remove', actor=current_user, trace_id=getattr(request.state, 'trace_id', None),
                 details={'member_id': member_id})
    return {'removed': True}


def _invite_for(db: Session, token: str) -> TeamMember:
    row = db.query(TeamMember).filter(TeamMember.token_hash == hash_token(token)).first()
    if not row or row.status != 'invited':
        raise HTTPException(404, 'This invite link is not valid. It may have been used or cancelled. '
                                 'Ask the team owner to send a new one.')
    if row.expired:
        raise HTTPException(410, 'This invite has expired. Ask the team owner to send a new one.')
    return row


@router.get('/invite')
def preview_invite(token: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    row = _invite_for(db, token)
    owner = db.get(User, row.owner_id)
    return {'owner': {'name': _name(owner)}, 'email': row.email,
            'email_matches': canonical_email(current_user.email) == row.email_canonical,
            'expires_at': row.expires_at.isoformat() if row.expires_at else None}


@router.post('/accept')
def accept(body: TokenBody, request: Request, db: Session = Depends(get_db),
           current_user: User = Depends(get_current_user)):
    row = _invite_for(db, body.token)
    if canonical_email(current_user.email) != row.email_canonical:
        raise HTTPException(403, f'This invite was sent to {row.email}. Sign in with that email address to accept it.')
    if db.query(TeamMember).filter(TeamMember.user_id == current_user.id, TeamMember.status == 'active').first():
        raise HTTPException(409, 'You are already on a team. Leave it in Settings before joining another.')
    if db.query(TeamMember).filter(TeamMember.owner_id == current_user.id).first():
        raise HTTPException(409, 'You manage your own team, so you cannot join another one.')
    row.user_id = current_user.id
    row.status = 'active'
    row.accepted_at = datetime.utcnow()
    row.token_hash = None
    db.commit()
    record_event('team.join', actor=current_user, trace_id=getattr(request.state, 'trace_id', None),
                 details={'member_id': row.id})
    owner = db.get(User, row.owner_id)
    return {'joined': True, 'owner': {'name': _name(owner)}}


@router.post('/leave')
def leave(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    row = db.query(TeamMember).filter(TeamMember.user_id == current_user.id, TeamMember.status == 'active').first()
    if not row:
        raise HTTPException(404, 'You are not on a team.')
    db.delete(row)
    db.commit()
    record_event('team.leave', actor=current_user, trace_id=getattr(request.state, 'trace_id', None),
                 details={'member_id': row.id})
    return {'left': True}
