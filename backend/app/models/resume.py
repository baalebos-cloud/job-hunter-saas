from sqlalchemy import Column, Integer, String, Text, ForeignKey, Float, JSON, LargeBinary
from sqlalchemy.orm import relationship
from backend.app.database import Base

class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True) # Set nullable if you haven't built Auth yet

    filename = Column(String, nullable=False)
    
    # Use LargeBinary to store the raw PDF/Word bytes securely
    content = Column(LargeBinary, nullable=False) 
    
    # Keep parsed_data as Text for general notes
    parsed_data = Column(Text, nullable=True)

    # --- PERSISTENT AI DATA ---
    # The overall 96% match score
    ats_score = Column(Float, default=0.0)
    
    # This stores the ENTIRE breakdown from your screenshot:
    # { "technical_skills": {"score": 89, "count": "17/20"}, "missing": ["Oracle", "OCI"] ... }
    analysis_data = Column(JSON, nullable=True) 
    # --------------------------

    user = relationship("User")
