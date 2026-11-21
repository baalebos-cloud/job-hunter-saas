"""Help & support requests and their conversation threads."""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import relationship

from backend.app.database import Base

CATEGORIES = ('question', 'bug', 'feedback', 'billing', 'account', 'resume', 'jobs', 'other')
STATUSES = ('open', 'answered', 'solved')


class SupportTicket(Base):
    __tablename__ = 'support_tickets'

    id = Column(Integer, primary_key=True)
    # Signed-out visitors can write too; their email is the only contact.
    user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    email = Column(String(255), nullable=False, index=True)
    name = Column(String(120), nullable=True)
    category = Column(String(20), nullable=False, default='question')
    subject = Column(String(160), nullable=False)
    status = Column(String(12), nullable=False, default='open', index=True)
    # Context captured automatically when the request is sent.
    page = Column(String(300), nullable=True)
    user_agent = Column(String(300), nullable=True)
    attachment = Column(LargeBinary, nullable=True)
    attachment_type = Column(String(40), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_reply_at = Column(DateTime, nullable=True)       # last answer from support

    messages = relationship('SupportMessage', back_populates='ticket', cascade='all, delete-orphan',
                            order_by='SupportMessage.id')

    @property
    def number(self) -> str:
        return f'BB-{self.id:05d}'


class SupportMessage(Base):
    __tablename__ = 'support_messages'

    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey('support_tickets.id', ondelete='CASCADE'), nullable=False, index=True)
    author = Column(String(10), nullable=False)          # 'user' | 'support'
    staff_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    ticket = relationship('SupportTicket', back_populates='messages')
