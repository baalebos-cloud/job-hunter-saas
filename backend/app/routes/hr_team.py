"""Employer workspace: the team, invitations and each job's hiring team.

Admins invite teammates by email with a role. The invite link is single-use,
stored hashed and expires after seven days. Accepting creates an employer
account for that email (the link proves the address), or adds an existing
employer account that is not in a company. Candidate accounts cannot join:
an employer account sees other people's applications, so it is kept separate.
"""
import re
from datetime import datetime, timedelta
from html import escape

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.database import get_db
from backend.app.models.company import (INVITE_DAYS, JOB_ROLES, MAX_MEMBERS, ROLES, CompanyMember,
                                        JobTeamMember)
from backend.app.models.user import User
from backend.app.services.account_integrity import canonical_email, is_disposable
from backend.app.services.audit import record_event
from backend.app.services.auth_service import hash_password, hash_token, new_opaque_token, verify_password
from backend.app.services.workspace import Member, job_for, member_for, require_permission

router = APIRouter(tags=['Employer workspace'])

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
ROLE_LABELS = {'admin': 'Admin', 'recruiter': 'Recruiter', 'hiring_manager': 'Hiring manager',
               'interviewer': 'Interviewer'}


class InviteBody(BaseModel):
    email: str = Field(..., max_length=255)
    role: str = Field('recruiter', max_length=20)


class RoleBody(BaseModel):
    role: str = Field(..., max_length=20)


class AcceptBody(BaseModel):
    token: str = Field(..., min_length=10, max_length=200)
    password: str = Field(..., min_length=1, max_length=200)
    full_name: str | None = Field(None, max_length=120)


class HiringTeamBody(BaseModel):
    members: list[dict] = Field(default_factory=list, max_length=MAX_MEMBERS)


def _limit(key: str, limit: int, window: int):
    from backend.app.core.rate_limit import hit
    allowed, retry = hit(key, limit, window)
    if not allowed:
        raise HTTPException(429, 'Too many changes in a short time. Please wait a few minutes and try again.',
                            headers={'Retry-After': str(retry)})


def _role(value: str) -> str:
    if value not in ROLES:
        raise HTTPException(400, 'Choose a role: Admin, Recruiter, Hiring manager or Interviewer.')
    return value


def _name(user: User | None) -> str | None:
    return (user.full_name or user.email.split('@')[0]) if user else None


def _serialize(row: CompanyMember, db: Session, me: User) -> dict:
    user = db.get(User, row.user_id) if row.user_id else None
    return {'id': row.id, 'user_id': row.user_id, 'email': row.email, 'name': _name(user), 'role': row.role,
            'role_label': ROLE_LABELS.get(row.role, row.role),
            'status': 'expired' if row.expired else row.status, 'is_you': row.user_id == me.id,
            'invited_at': row.invited_at.isoformat() if row.invited_at else None,
            'accepted_at': row.accepted_at.isoformat() if row.accepted_at else None}


def _admins(db: Session, company_id: int) -> int:
    return db.query(CompanyMember).filter(CompanyMember.company_id == company_id, CompanyMember.role == 'admin',
                                          CompanyMember.status == 'active').count()


def _member_row(db: Session, member: Member, member_id: int) -> CompanyMember:
    row = db.query(CompanyMember).filter(CompanyMember.id == member_id,
                                         CompanyMember.company_id == member.company.id).first()
    if not row:
        raise HTTPException(404, 'Team member not found.')
    return row


def _issue(row: CompanyMember) -> str:
    raw, digest = new_opaque_token()
    row.token_hash = digest
    row.invited_at = datetime.utcnow()
    row.expires_at = row.invited_at + timedelta(days=INVITE_DAYS)
    return raw


def _send_invite(inviter: str, company: str, row: CompanyMember, raw_token: str):
    from backend.app.utils import email
    link = f"{settings.FRONTEND_URL.rstrip('/')}/hr/join?token={raw_token}"
    role = ROLE_LABELS.get(row.role, row.role)
    html = f"""<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;background:#fbfaf7;padding:32px 16px;color:#0b1324">
<div style="max-width:560px;margin:0 auto;background:#fff;border:1px solid #e7e3da;border-radius:12px;padding:28px">
<p style="font-size:18px;font-weight:800;margin:0 0 16px">baalebos<span style="color:#10b981">.</span></p>
<h1 style="font-size:20px;margin:0 0 12px">{escape(inviter)} invited you to join {escape(company)} on Baalebos</h1>
<p style="font-size:14px;line-height:1.6;margin:0 0 20px">You’ll join as <strong>{escape(role)}</strong> and work on
{escape(company)}’s jobs and applicants with the rest of the hiring team.</p>
<p style="margin:0 0 20px"><a href="{escape(link)}" style="background:#0b1324;color:#fff;text-decoration:none;font-weight:bold;
padding:12px 20px;border-radius:8px;display:inline-block">Accept the invitation</a></p>
<p style="font-size:12px;color:#64748b;line-height:1.6;margin:0">This link is for <strong>{escape(row.email)}</strong>,
works once and expires in {INVITE_DAYS} days. If you weren’t expecting it, you can ignore this email.</p>
</div><p style="text-align:center;font-size:11px;color:#94a3b8">Baalebos · {escape(settings.SUPPORT_EMAIL)}</p>
</body></html>"""
    email.send_account_message(row.email, f'{inviter} invited you to join {company} on Baalebos', html)


# ── Workspace ────────────────────────────────────────────────────────────────

@router.get('/workspace')
def workspace(member: Member = Depends(member_for)):
    """Who I am in my company: used by the portal to show only what my role can do."""
    return {'company': {'id': member.company.id, 'name': member.company.name},
            'role': member.role, 'role_label': ROLE_LABELS.get(member.role, member.role),
            'permissions': {p: member.can(p) for p in ('manage_team', 'post_jobs', 'all_jobs', 'move_candidates')}}


@router.get('/team')
def team(db: Session = Depends(get_db), member: Member = Depends(member_for)):
    rows = (db.query(CompanyMember).filter(CompanyMember.company_id == member.company.id)
            .order_by(CompanyMember.status, CompanyMember.invited_at).all())
    visible = rows if member.can('manage_team') else [r for r in rows if r.status == 'active']
    return {'can_manage': member.can('manage_team'), 'max_members': MAX_MEMBERS,
            'roles': [{'value': r, 'label': ROLE_LABELS[r]} for r in ROLES],
            'members': [_serialize(r, db, member.user) for r in visible]}


@router.post('/team/invites', status_code=201)
def invite(body: InviteBody, background: BackgroundTasks, request: Request, db: Session = Depends(get_db),
           member: Member = Depends(require_permission('manage_team'))):
    role = _role(body.role)
    address = body.email.strip().lower()
    if not EMAIL_RE.match(address):
        raise HTTPException(400, 'Enter a valid email address.')
    if is_disposable(address, db):
        raise HTTPException(400, 'Temporary email addresses can’t be invited. Use a work email.')
    canon = canonical_email(address)
    existing = db.query(CompanyMember).filter(CompanyMember.company_id == member.company.id,
                                              CompanyMember.email_canonical == canon).first()
    if existing and not existing.expired:
        raise HTTPException(409, 'This person is already on your team or has a pending invitation.')
    elsewhere = (db.query(CompanyMember).filter(CompanyMember.email_canonical == canon, CompanyMember.status == 'active',
                                                CompanyMember.company_id != member.company.id).first())
    account = db.query(User).filter(User.email_canonical == canon).first() or \
        db.query(User).filter(User.email == address).first()
    if elsewhere or (account and account.is_hr and account.hr_approved):
        raise HTTPException(409, 'This email already belongs to another company’s employer account.')
    if account and not account.is_hr:
        raise HTTPException(409, 'This email is used by a candidate account. Invite their work email instead.')
    if not existing and db.query(CompanyMember).filter(CompanyMember.company_id == member.company.id).count() >= MAX_MEMBERS:
        raise HTTPException(400, f'Your team has reached {MAX_MEMBERS} people. Remove someone or cancel an invitation first.')
    _limit(f'company-invite:{member.company.id}', 50, 3600)
    row = existing or CompanyMember(company_id=member.company.id, email=address, email_canonical=canon)
    row.role = role
    row.status = 'invited'
    row.invited_by = member.user.id
    raw = _issue(row)
    db.add(row)
    db.commit()
    background.add_task(_send_invite, _name(member.user), member.company.name, row, raw)
    record_event('company.invite', actor=member.user, trace_id=getattr(request.state, 'trace_id', None),
                 details={'company_id': member.company.id, 'member_id': row.id, 'role': role})
    return _serialize(row, db, member.user)


@router.post('/team/invites/{member_id}/resend')
def resend(member_id: int, background: BackgroundTasks, db: Session = Depends(get_db),
           member: Member = Depends(require_permission('manage_team'))):
    row = _member_row(db, member, member_id)
    if row.status != 'invited':
        raise HTTPException(409, 'This person has already joined.')
    _limit(f'company-invite:{member.company.id}', 50, 3600)
    raw = _issue(row)
    db.commit()
    background.add_task(_send_invite, _name(member.user), member.company.name, row, raw)
    return _serialize(row, db, member.user)


@router.patch('/team/members/{member_id}')
def change_role(member_id: int, body: RoleBody, request: Request, db: Session = Depends(get_db),
                member: Member = Depends(require_permission('manage_team'))):
    row = _member_row(db, member, member_id)
    role = _role(body.role)
    if row.role == 'admin' and role != 'admin' and row.status == 'active' and _admins(db, member.company.id) <= 1:
        raise HTTPException(400, 'Your company needs at least one admin. Make someone else an admin first.')
    row.role = role
    db.commit()
    record_event('company.role_change', actor=member.user, trace_id=getattr(request.state, 'trace_id', None),
                 details={'company_id': member.company.id, 'member_id': row.id, 'role': role})
    return _serialize(row, db, member.user)


@router.delete('/team/members/{member_id}')
def remove(member_id: int, request: Request, db: Session = Depends(get_db),
           member: Member = Depends(require_permission('manage_team'))):
    """Remove a teammate (they lose employer access and are signed out) or cancel an invitation."""
    row = _member_row(db, member, member_id)
    if row.role == 'admin' and row.status == 'active' and _admins(db, member.company.id) <= 1:
        raise HTTPException(400, 'Your company needs at least one admin. Make someone else an admin first.')
    if row.user_id:
        user = db.get(User, row.user_id)
        if user:
            user.hr_approved = False                         # no employer access without a company
            user.token_version = (user.token_version or 0) + 1   # signs them out everywhere
        db.query(JobTeamMember).filter(JobTeamMember.user_id == row.user_id).delete(synchronize_session=False)
    db.delete(row)
    db.commit()
    record_event('company.remove', actor=member.user, trace_id=getattr(request.state, 'trace_id', None),
                 details={'company_id': member.company.id, 'member_id': member_id})
    return {'removed': True}


# ── Accepting an invitation (no sign-in needed: the link proves the email) ────

def _invite_for(db: Session, token: str) -> CompanyMember:
    row = db.query(CompanyMember).filter(CompanyMember.token_hash == hash_token(token)).first()
    if not row or row.status != 'invited':
        raise HTTPException(404, 'This invitation link isn’t valid. It may have been used or cancelled. '
                                 'Ask your company admin to send a new one.')
    if row.expired:
        raise HTTPException(410, 'This invitation has expired. Ask your company admin to send a new one.')
    return row


def _account(db: Session, row: CompanyMember) -> User | None:
    return db.query(User).filter(User.email_canonical == row.email_canonical).first() or \
        db.query(User).filter(User.email == row.email).first()


@router.get('/team/invite')
def preview_invite(token: str, db: Session = Depends(get_db)):
    from backend.app.models.company import Company
    row = _invite_for(db, token)
    company = db.get(Company, row.company_id)
    account = _account(db, row)
    return {'company': company.name if company else None, 'email': row.email, 'role': row.role,
            'role_label': ROLE_LABELS.get(row.role, row.role),
            'has_account': bool(account), 'candidate_account': bool(account and not account.is_hr),
            'expires_at': row.expires_at.isoformat() if row.expires_at else None}


@router.post('/team/accept')
def accept(body: AcceptBody, request: Request, db: Session = Depends(get_db)):
    from backend.app.models.company import Company
    _limit(f'company-accept:{getattr(request.client, "host", "")}', 20, 900)
    row = _invite_for(db, body.token)
    company = db.get(Company, row.company_id)
    account = _account(db, row)
    if account and not account.is_hr:
        raise HTTPException(409, 'This email is used by a candidate account, which can’t join a company. '
                                 'Ask your admin to invite your work email.')
    if account and db.query(CompanyMember).filter(CompanyMember.user_id == account.id,
                                                  CompanyMember.status == 'active').first():
        raise HTTPException(409, 'This account already belongs to a company.')
    if account and account.hr_approved:
        raise HTTPException(409, 'This email already has its own employer account.')
    if account:
        if not verify_password(body.password, account.hashed_password):
            raise HTTPException(401, 'That password doesn’t match the existing account for this email.')
        user = account
    else:
        name = (body.full_name or '').strip()
        if not name:
            raise HTTPException(400, 'Enter your full name.')
        if len(body.password) < 8:
            raise HTTPException(400, 'Password must be at least 8 characters.')
        user = User(email=row.email, email_canonical=row.email_canonical, full_name=name[:120],
                    hashed_password=hash_password(body.password))
        db.add(user)
    user.is_hr = True
    user.is_verified = True              # the single-use link was delivered to this address
    user.verification_token = None
    user.hr_approved = True              # vouched for by the company admin
    user.company_name = company.name if company else user.company_name
    db.flush()
    row.user_id = user.id
    row.status = 'active'
    row.accepted_at = datetime.utcnow()
    row.token_hash = None
    db.commit()
    record_event('company.join', actor=user, trace_id=getattr(request.state, 'trace_id', None),
                 details={'company_id': row.company_id, 'member_id': row.id, 'role': row.role})
    return {'joined': True, 'company': company.name if company else None, 'email': user.email}


# ── Hiring team of a job ─────────────────────────────────────────────────────

def _hiring_team(db: Session, job_id: int) -> list[dict]:
    rows = db.query(JobTeamMember).filter(JobTeamMember.job_id == job_id).order_by(JobTeamMember.id).all()
    users = {u.id: u for u in db.query(User).filter(User.id.in_([r.user_id for r in rows] or [-1]))}
    return [{'user_id': r.user_id, 'name': _name(users.get(r.user_id)),
             'email': users[r.user_id].email if r.user_id in users else None, 'role': r.role} for r in rows]


@router.get('/jobs/{job_id}/team')
def get_hiring_team(job_id: int, db: Session = Depends(get_db), member: Member = Depends(member_for)):
    job_for(db, member, job_id)
    return {'members': _hiring_team(db, job_id), 'roles': list(JOB_ROLES)}


@router.put('/jobs/{job_id}/team')
def set_hiring_team(job_id: int, body: HiringTeamBody, request: Request, db: Session = Depends(get_db),
                    member: Member = Depends(require_permission('post_jobs'))):
    job = job_for(db, member, job_id)
    company_users = {r.user_id for r in db.query(CompanyMember.user_id).filter(
        CompanyMember.company_id == member.company.id, CompanyMember.status == 'active')}
    wanted: dict[int, str] = {}
    for entry in body.members:
        try:
            user_id = int(entry.get('user_id'))
        except (TypeError, ValueError):
            raise HTTPException(400, 'Each hiring team entry needs a teammate.') from None
        role = entry.get('role')
        if role not in JOB_ROLES:
            raise HTTPException(400, 'Hiring team roles are recruiter, coordinator, hiring manager or interviewer.')
        if user_id not in company_users:
            raise HTTPException(400, 'Only people on your company team can be on a hiring team.')
        wanted[user_id] = role
    db.query(JobTeamMember).filter(JobTeamMember.job_id == job.id).delete(synchronize_session=False)
    db.add_all([JobTeamMember(job_id=job.id, user_id=u, role=r) for u, r in wanted.items()])
    db.commit()
    record_event('job.hiring_team', actor=member.user, trace_id=getattr(request.state, 'trace_id', None),
                 details={'job_id': job.id, 'members': len(wanted)})
    return {'members': _hiring_team(db, job.id)}
