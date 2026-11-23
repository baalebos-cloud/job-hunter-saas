"""Enterprise team access: an Enterprise owner shares the plan with up to 9 people.

One row per invited email. The row starts as ``invited`` (a hashed, single-use
token that expires) and becomes ``active`` once the invitee signs in with that
email address and accepts. Each person's resumes stay private to them; the team
only shares the plan.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from backend.app.database import Base

TEAM_SEATS = 10                    # the owner plus 9 invited people
INVITE_DAYS = 7


class TeamMember(Base):
    __tablename__ = 'team_members'
    __table_args__ = (UniqueConstraint('owner_id', 'email_canonical', name='uq_team_owner_email'),)

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    email = Column(String(255), nullable=False)
    email_canonical = Column(String(255), nullable=False, index=True)
    # Set when the invite is accepted. A person can belong to one team at a time.
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=True, unique=True)
    status = Column(String(10), nullable=False, default='invited')       # invited | active
    token_hash = Column(String(64), nullable=True, unique=True)
    invited_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    accepted_at = Column(DateTime, nullable=True)

    @property
    def expired(self) -> bool:
        return self.status == 'invited' and (self.expires_at is None or self.expires_at < datetime.utcnow())
