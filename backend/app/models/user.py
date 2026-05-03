from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.app.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    career_track = Column(String, nullable=True)
    country = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False)
    is_hr = Column(Boolean, default=False)
    company_name = Column(String, nullable=True)  # for HR users
    created_at = Column(DateTime, default=datetime.utcnow)

    resumes = relationship("Resume", back_populates="owner")
    applications = relationship("Application", back_populates="user")
    outreach_messages = relationship("OutreachMessage", back_populates="user")


class OutreachMessage(Base):
    __tablename__ = "outreach_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    message = Column(Text, nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow)
    delivered = Column(Boolean, default=False)

    user = relationship("User", back_populates="outreach_messages")
    application = relationship("Application", back_populates="outreach_messages")
