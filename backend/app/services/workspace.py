"""Employer workspace: who belongs to which company and what each role may do.

``member_for`` is the single entry point used by the employer routes. An approved
employer account without a workspace (created before workspaces existed, or by an
older code path) gets one on first use, with the jobs they posted moved into it,
so nobody loses access to anything they had.
"""
from dataclasses import dataclass
from datetime import datetime

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.dependencies.roles import is_owner, require_hr
from backend.app.models.company import Company, CompanyMember, JobTeamMember
from backend.app.models.job import Job
from backend.app.models.user import User
from backend.app.services.account_integrity import canonical_email

# What each company role may do across the workspace.
PERMISSIONS = {
    'admin':          {'manage_team', 'post_jobs', 'all_jobs', 'move_candidates'},
    'recruiter':      {'post_jobs', 'all_jobs', 'move_candidates'},
    'hiring_manager': {'move_candidates'},
    'interviewer':    set(),
}


@dataclass
class Member:
    user: User
    company: Company
    role: str
    platform_owner: bool = False      # Baalebos super admin acting with full access

    def can(self, permission: str) -> bool:
        return self.platform_owner or permission in PERMISSIONS.get(self.role, set())


def ensure_workspace(db: Session, user: User) -> CompanyMember:
    """The user's active membership, creating a company for an employer that has none."""
    membership = (db.query(CompanyMember)
                  .filter(CompanyMember.user_id == user.id, CompanyMember.status == 'active').first())
    if membership:
        return membership
    company = Company(name=(user.company_name or user.email.split('@')[-1]).strip()[:200],
                      website=user.company_url, country=user.country, created_by=user.id,
                      approved_at=datetime.utcnow() if user.hr_approved else None)
    db.add(company)
    db.flush()
    membership = CompanyMember(company_id=company.id, user_id=user.id, email=user.email.lower(),
                               email_canonical=canonical_email(user.email), role='admin', status='active',
                               accepted_at=datetime.utcnow())
    db.add(membership)
    (db.query(Job).filter(Job.hr_user_id == user.id, Job.company_id.is_(None))
     .update({Job.company_id: company.id}, synchronize_session=False))
    db.commit()
    return membership


def member_for(db: Session = Depends(get_db), user: User = Depends(require_hr)) -> Member:
    membership = ensure_workspace(db, user)
    company = db.get(Company, membership.company_id)
    return Member(user=user, company=company, role=membership.role, platform_owner=is_owner(user))


def require_permission(permission: str):
    def dependency(member: Member = Depends(member_for)) -> Member:
        if not member.can(permission):
            raise HTTPException(403, _denied(permission))
        return member
    return dependency


def _denied(permission: str) -> str:
    return {'manage_team': 'Only company admins can manage the team.',
            'post_jobs': 'Only admins and recruiters can post or edit jobs.',
            'move_candidates': 'Your role cannot change a candidate’s status.'}.get(permission, 'Not allowed.')


def assigned_job_ids(db: Session, member: Member) -> set[int]:
    return {row.job_id for row in db.query(JobTeamMember.job_id).filter(JobTeamMember.user_id == member.user.id)}


def visible_jobs(db: Session, member: Member):
    """Jobs this person can see: every company job for admins and recruiters, only
    hiring-team jobs for hiring managers and interviewers."""
    query = db.query(Job).filter(Job.company_id == member.company.id)
    if not member.can('all_jobs'):
        query = query.filter(Job.id.in_(assigned_job_ids(db, member) or {-1}))
    return query


def job_for(db: Session, member: Member, job_id: int) -> Job:
    """A job this person may access, else 404 (never reveal other companies' jobs)."""
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, 'Job not found')
    if member.platform_owner:
        return job
    if job.company_id != member.company.id:
        raise HTTPException(404, 'Job not found')
    if not member.can('all_jobs') and job.id not in assigned_job_ids(db, member):
        raise HTTPException(404, 'Job not found')
    return job
