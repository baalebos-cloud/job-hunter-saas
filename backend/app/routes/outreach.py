from fastapi import APIRouter, HTTPException
from backend.app.services.outreach_service import generate_message

router = APIRouter(
    prefix="/outreach",
    tags=["Outreach"]
)

@router.post("/generate")
def create_outreach(job_url: str, candidate_name: str, resume_text: str):
    """
    Generate a personalized recruiter message for a given job.
    """
    try:
        message = generate_message(job_url, candidate_name, resume_text)
        return {"message": message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
