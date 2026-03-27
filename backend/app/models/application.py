from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.app.database import Base

class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # --- THE LINK TO JOBS ---
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    # ------------------------

    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    ats_score = Column(Float, nullable=True)
    
    # Relationships for easy access in code
    user = relationship("User")
    job = relationship("Job") 
