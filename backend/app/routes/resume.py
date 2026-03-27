import os
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.orm import Session
from celery.result import AsyncResult

from backend.app.database import get_db
from backend.app.tasks import process_resume_task
from backend.app.celery_app import celery_app

router = APIRouter(
    prefix="/resume",
    tags=["Resume"]
)

@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    job_description: str = Form(...),
    # Changed from 'track' to 'job_title' to support Global Tech fields
    job_title: str = Form(...),
    user_email: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Upload a resume (PDF or DOCX) for ANY global tech role. 
    Processing is handled asynchronously via Celery to calculate an accurate ATS score.
    """

    # 1. Expanded Validation: Support PDF and Word for Global Standards
    allowed_extensions = [".pdf", ".docx", ".doc"]
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Baalebos AI supports: {', '.join(allowed_extensions)}"
        )

    # 2. Read file content into memory for the Celery worker
    file_content = await file.read()
    filename = file.filename

    # 3. Contextual Data for the Task
    user_context = {"email": user_email}

    # 🚀 Trigger Global Celery Task
    # We pass the dynamic job_title and the filename so the worker knows how to parse it
    task = process_resume_task.delay(
        file_content,
        filename,
        job_description,
        user_email,
        job_title.strip(),
        user_context
    )

    return {
        "message": f"Baalebos AI is analyzing your profile for: {job_title}",
        "task_id": task.id,
        "filename": filename
    }


@router.get("/status/{task_id}")
def get_resume_status(task_id: str):
    """
    Check the status of the ATS calculation and NLP matching.
    """
    task_result = AsyncResult(task_id, app=celery_app)

    # Map Celery states to user-friendly status strings
    status_map = {
        "PENDING": "pending",
        "STARTED": "processing",
        "SUCCESS": "completed",
        "FAILURE": "failed"
    }

    current_status = status_map.get(task_result.state, task_result.state.lower())

    response = {
        "task_id": task_id,
        "status": current_status,
        "result": task_result.result if current_status == "completed" else None
    }

    # Include error details if the analysis failed
    if current_status == "failed":
        response["error"] = str(task_result.result)

    return response
