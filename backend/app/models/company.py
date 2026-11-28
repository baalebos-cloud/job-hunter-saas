"""Employer workspaces (the ATS foundation).

A company is created when an employer signs up; its first person is its Admin.
The Admin invites teammates by email with a role:

* ``admin``          everything, including the team and company settings
* ``recruiter``      every job and candidate; posts and edits jobs
* ``hiring_manager`` only jobs they are on the hiring team for; can move candidates
* ``interviewer``    only jobs they are on the hiring team for; read-only for now

A person belongs to one company. Invite links are single-use, stored hashed and
expire after ``INVITE_DAYS``.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from backend.app.database import Base

ROLES = ('admin', 'recruiter', 'hiring_manager', 'interviewer')
JOB_ROLES = ('recruiter', 'coordinator', 'hiring_manager', 'interviewer')
INVITE_DAYS = 7
MAX_MEMBERS = 50          # people (active or invited) per company


class Company(Base):
    __tablename__ = 'companies'

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    website = Column(String(255), nullable=True)
    country = Column(String(100), nullable=True)
    created_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    # Set when Baalebos approves the employer; teammates can only be invited after that.
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CompanyMember(Base):
    __tablename__ = 'company_members'
    __table_args__ = (UniqueConstraint('company_id', 'email_canonical', name='uq_company_member_email'),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True)
    # Set once the invite is accepted. One company per person.
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=True, unique=True)
    email = Column(String(255), nullable=False)
    email_canonical = Column(String(255), nullable=False, index=True)
    role = Column(String(20), nullable=False, default='recruiter')
    status = Column(String(10), nullable=False, default='invited')        # invited | active
    token_hash = Column(String(64), nullable=True, unique=True)
    invited_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    invited_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    accepted_at = Column(DateTime, nullable=True)

    @property
    def expired(self) -> bool:
        return self.status == 'invited' and (self.expires_at is None or self.expires_at < datetime.utcnow())


class JobTeamMember(Base):
    """The hiring team of one job: who works on it and in which capacity."""
    __tablename__ = 'job_team_members'
    __table_args__ = (UniqueConstraint('job_id', 'user_id', name='uq_job_team_user'),)

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow, nullable=False)
