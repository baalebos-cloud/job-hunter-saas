from sqlalchemy import Column, Integer, String, Text, ForeignKey, Float, JSON, LargeBinary
from sqlalchemy.orm import relationship
from backend.app.database import Base

class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    
    # FK linking to the User table
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    filename = Column(String, nullable=False)
    content = Column(LargeBinary, nullable=False)
    parsed_data = Column(Text, nullable=True)
    ats_score = Column(Float, default=0.0)
    analysis_data = Column(JSON, nullable=True)

    # This name 'owner' MUST match the 'back_populates' in user.py
    owner = relationship("User", back_populates="resumes")
