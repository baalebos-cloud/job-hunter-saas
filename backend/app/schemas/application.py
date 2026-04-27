from pydantic import BaseModel
from datetime import datetime

class ApplicationResponse(BaseModel):
    id: int
    user_id: int
    job_id: int
    status: str
    match_score: float
    created_at: datetime

    model_config = {
        "from_attributes": True
    }
