from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.app.database import Base

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    company = Column(String, index=True)
    location = Column(String, nullable=True)
    category = Column(String, index=True)
    url = Column(String, nullable=True)
    source = Column(String, nullable=True)
    description = Column(String, nullable=True)
    salary_range = Column(String, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    scraped_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    work_type = Column(String, nullable=True)  # remote | hybrid | onsite
    posted_by_hr = Column(Boolean, default=False)  # True = HR posted, False = scraped
    hr_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # HR who posted

    applications = relationship("Application", back_populates="job")