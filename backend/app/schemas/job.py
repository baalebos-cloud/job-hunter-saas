from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class JobCreate(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    description: Optional[str] = None


class JobResponse(BaseModel):
    id: int
    title: str
    company: str
    location: Optional[str] = None
    description: Optional[str] = None
    salary_range: Optional[str] = None
    user_id: Optional[int] = None
    source: Optional[str] = None
    category: Optional[str] = None
    url: Optional[str] = None
    work_type: Optional[str] = None
    scraped_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
