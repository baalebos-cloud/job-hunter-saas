from pydantic import BaseModel


class JobCreate(BaseModel):
    title: str
    company: str
    location: str
    description: str


class JobResponse(BaseModel):
    id: int
    title: str
    company: str
    location: str
    description: str
    user_id: int

    model_config = {"from_attributes": True}
