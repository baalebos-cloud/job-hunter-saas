from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ApplicationResponse(BaseModel):
    id: int
    user_id: int
    job_id: int
    status: str
    ats_score: Optional[float] = None
    created_at: datetime

    model_config = {
        "from_attributes": True
    }
