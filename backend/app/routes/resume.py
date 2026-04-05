import os
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.orm import Session
from celery.result import AsyncResult

from backend.app.database import get_db
from backend.app.dependencies.auth import get_current_user
# 🚀 IMPORT SPECIFIC TASK
from backend.app.tasks.resume_tasks import process_resume_task
from backend.app.celery_app import celery_app
from backend.app.models.user import User

router = APIRouter(
    prefix="/resume",
    tags=["Resume"]
)

@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    job_description: str = Form(...),
    job_title: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    allowed_extensions = [".pdf", ".docx", ".doc"]
    file_ext = os.path.splitext(file.filename).lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    file_content = await file.read()

    # 🚀 SEND EXACTLY 5 ARGUMENTS
    task = process_resume_task.delay(
        file_content,
        file.filename,
        job_description,
        current_user.id,
        job_title.strip()
    )

    # Convert task.id to string to ensure JSON compatibility
    return {
        "message": f"Baalebos AI analyzing: {job_title}",
        "task_id": str(task.id), 
        "filename": file.filename
    }

@router.get("/status/{task_id}")
def get_resume_status(task_id: str):
    task_result = AsyncResult(task_id, app=celery_app)
    
    status_map = {
        "PENDING": "pending",
        "STARTED": "processing",
        "SUCCESS": "completed",
        "FAILURE": "failed"
    }
    
    current_status = status_map.get(task_result.state, task_result.state.lower())

    return {
        "task_id": task_id,
        "status": current_status,
        "result": task_result.result if current_status == "completed" else None
    }
