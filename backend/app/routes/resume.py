import os
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from celery.result import AsyncResult

from backend.app.database import get_db
from backend.app.dependencies.auth import get_current_user
from backend.app.tasks.resume_tasks import process_resume_task
from backend.app.celery_app import celery_app
from backend.app.models.user import User

router = APIRouter(
    tags=["Resume"]
)

# FIX: Single source of truth for output dir — matches worker_tasks/resume_tasks.py
OUTPUT_DIR = "/app/output"


@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    job_description: str = Form(...),
    job_title: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    allowed_extensions = [".pdf", ".docx", ".doc"]
    file_ext = os.path.splitext(file.filename)[1].lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    file_content = await file.read()

    try:
        task = process_resume_task.delay(
            list(file_content),  # convert bytes to list for JSON serialization
            file.filename,
            job_description,
            current_user.id,
            job_title.strip()
        )
    except Exception as e:
        print(f"Celery task error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to queue analysis task. Please check worker is running. Error: {str(e)}"
        )

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


@router.get("/download/{task_id}")
async def download_resume(task_id: str, db: Session = Depends(get_db)):
    from backend.app.models.resume import Resume
    from fastapi.responses import Response

    # 1. Try filesystem first (local dev)
    file_path = os.path.join(OUTPUT_DIR, f"optimized_{task_id}.pdf")
    if os.path.exists(file_path):
        return FileResponse(
            path=file_path,
            media_type='application/pdf',
            filename=f"Baalebos_Optimized_{task_id}.pdf"
        )

    # 2. Try PostgreSQL (Railway production)
    resume = db.query(Resume).filter(
        Resume.filename == f"optimized_{task_id}.pdf"
    ).order_by(Resume.id.desc()).first()

    if resume and resume.content:
        return Response(
            content=resume.content,
            media_type='application/pdf',
            headers={"Content-Disposition": f'attachment; filename="Baalebos_Optimized_{task_id}.pdf"'}
        )

    raise HTTPException(
        status_code=404,
        detail="Optimized resume not found. It may still be generating."
    )