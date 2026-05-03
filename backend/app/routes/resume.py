import uuid
from fastapi.concurrency import run_in_threadpool
import os
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.dependencies.auth import get_current_user
from backend.app.models.user import User
from backend.app.models.resume import Resume

router = APIRouter(tags=["Resume"])

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/app/output")


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
    task_id = str(uuid.uuid4())

    # Run analysis directly (no Celery needed — works on Railway without Redis)
    def run_analysis():
        from backend.app.utils.ats_engine import analyze_detailed_ats, extract_text, rewrite_resume_for_job
        from backend.app.utils.pdf_generator import generate_optimized_resume

        resume_text = extract_text(file_content, file.filename)
        analysis = analyze_detailed_ats(
            file_content=file_content,
            filename=file.filename,
            job_description=job_description
        )
        ats_score    = analysis.get("overall_score", 0)
        missing_list = analysis.get("missing_list", [])
        suggestions  = analysis.get("suggestions", [])

        structured = rewrite_resume_for_job(
            resume_text=resume_text,
            job_description=job_description,
            job_title=job_title,
            missing_keywords=missing_list
        )

        improvements = []
        for s in suggestions[:5]:
            improvements.append({"skill": "AI Suggestion", "bullet_point": s})
        for kw in missing_list[:5]:
            if len(improvements) >= 10:
                break
            improvements.append({"skill": kw, "bullet_point": f"Add '{kw}' to your resume to boost ATS score."})

        pdf_buf = generate_optimized_resume(
            filename=file.filename,
            score=round(ats_score, 1),
            improvements=improvements,
            resume_text=resume_text,
            task_id=task_id,
            structured=structured,
        )
        return analysis, pdf_buf.read(), resume_text

    try:
        analysis, pdf_bytes, resume_text = await run_in_threadpool(run_analysis)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    # Save PDF to database
    try:
        resume_record = Resume(
            owner_id=current_user.id,
            filename=f"optimized_{task_id}.pdf",
            content=pdf_bytes,
            ats_score=analysis.get("overall_score", 0),
            analysis_data=analysis
        )
        db.add(resume_record)
        db.commit()
    except Exception as e:
        print(f"DB save warning: {e}")

    # Also save to filesystem for local dev
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(os.path.join(OUTPUT_DIR, f"optimized_{task_id}.pdf"), "wb") as f:
            f.write(pdf_bytes)
    except Exception:
        pass

    return {
        "message": f"Baalebos AI analyzed: {job_title}",
        "task_id": task_id,
        "filename": file.filename,
        "status": "completed",
        "result": {
            "id": task_id,
            "task_id": task_id,
            "resume_id": task_id,
            "overall_score": analysis.get("overall_score", 0),
            "ats_score": analysis.get("overall_score", 0),
            "keywords_matched": analysis.get("keywords_matched", 0),
            "keywords_missing": analysis.get("keywords_missing", 0),
            "total_keywords": analysis.get("total_keywords", 0),
            "missing_list": analysis.get("missing_list", []),
            "breakdown": analysis.get("breakdown", {}),
            "suggestions": analysis.get("suggestions", []),
            "job_title": job_title,
            "status": "success"
        }
    }


@router.get("/status/{task_id}")
def get_resume_status(task_id: str, db: Session = Depends(get_db)):
    # Check if result exists in DB
    resume = db.query(Resume).filter(
        Resume.filename == f"optimized_{task_id}.pdf"
    ).first()
    if resume:
        return {
            "task_id": task_id,
            "status": "completed",
            "result": resume.analysis_data
        }
    # Fallback to Celery if worker is running
    try:
        from celery.result import AsyncResult
        from backend.app.celery_app import celery_app
        task_result = AsyncResult(task_id, app=celery_app)
        status_map = {"PENDING": "pending", "STARTED": "processing", "SUCCESS": "completed", "FAILURE": "failed"}
        current_status = status_map.get(task_result.state, "pending")
        return {
            "task_id": task_id,
            "status": current_status,
            "result": task_result.result if current_status == "completed" else None
        }
    except Exception:
        return {"task_id": task_id, "status": "pending", "result": None}


@router.get("/download/{task_id}")
async def download_resume(task_id: str, db: Session = Depends(get_db)):
    # Try filesystem first
    file_path = os.path.join(OUTPUT_DIR, f"optimized_{task_id}.pdf")
    if os.path.exists(file_path):
        return FileResponse(path=file_path, media_type="application/pdf",
                            filename=f"Baalebos_Optimized_{task_id}.pdf")
    # Try database
    resume = db.query(Resume).filter(
        Resume.filename == f"optimized_{task_id}.pdf"
    ).first()
    if resume and resume.content:
        return Response(content=resume.content, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="Baalebos_Optimized_{task_id}.pdf"'})
    raise HTTPException(status_code=404, detail="Resume not found.")


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