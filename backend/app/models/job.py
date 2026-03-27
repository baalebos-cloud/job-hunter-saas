from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from backend.app.database import Base

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    company = Column(String, index=True)
    location = Column(String, nullable=False)
    category = Column(String, index=True)
    url = Column(String, unique=True, index=True)
    source = Column(String)
    description = Column(String)

    user_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User")
