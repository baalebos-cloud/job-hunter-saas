import uuid
import os
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import FileResponse, Response
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from backend.app.dependencies.plan_guard import require_scan_quota
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
    get_current_user: User = Depends(require_scan_quota),
    
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
        raise HTTPException(status_code=400, detail="Unsupported file type. Use PDF, DOCX or DOC.")

    file_content = await file.read()
    if len(file_content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 10MB.")

    if file_ext == ".pdf" and not file_content.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Invalid PDF file.")
    if file_ext == ".docx" and not file_content.startswith(b"PK\x03\x04"):
        raise HTTPException(status_code=400, detail="Invalid DOCX file.")

    task_id = str(uuid.uuid4())

    def run_analysis():
        from backend.app.utils.ats_engine import (
            analyze_detailed_ats,
            extract_text,
            extract_resume_data,
            rewrite_resume_for_job,
        )
        from backend.app.utils.pdf_generator import generate_optimized_resume

        # Step 1: Extract raw text
        resume_text = extract_text(file_content, file.filename)

        # Step 2: ATS scoring
        analysis    = analyze_detailed_ats(
            file_content=file_content,
            filename=file.filename,
            job_description=job_description
        )
        ats_score    = analysis.get("overall_score", 0)
        missing_list = analysis.get("missing_list", [])
        suggestions  = analysis.get("suggestions", [])

        # Step 3: Extract structured resume data for PDF generation
        resume_data = extract_resume_data(
            file_content=file_content,
            filename=file.filename,
            job_title=job_title
        )

        # Step 4: AI rewrite — optimise summary, experience, skills
        rewritten = rewrite_resume_for_job(
            resume_text=resume_text,
            job_description=job_description,
            job_title=job_title
        )

        # Merge rewritten sections into resume_data
        if rewritten and "error" not in rewritten:
            if rewritten.get("optimized_summary"):
                resume_data["summary"] = rewritten["optimized_summary"]
            if rewritten.get("optimized_experience"):
                resume_data["experience"] = rewritten["optimized_experience"]
            if rewritten.get("optimized_skills"):
                resume_data["skills"] = rewritten["optimized_skills"]

        # Step 5: Inject clean missing keywords for skills merge in pdf_generator
        def is_real_skill(kw: str) -> bool:
            kw = kw.strip()
            if len(kw) > 40:
                return False
            if any(kw.lower().startswith(p) for p in [
                "experience", "background", "relevant", "knowledge of",
                "familiarity", "understanding", "ability to", "proven",
                "strong", "excellent", "demonstrated", "add groq"
            ]):
                return False
            return True

        real_skills   = [kw for kw in missing_list if is_real_skill(kw)]
        resume_data["missing_keywords"] = real_skills

        # Step 6: Build improvements list
        improvements = []
        for kw in real_skills[:8]:
            improvements.append({"skill": kw, "bullet_point": f"Added to resume: {kw}"})
        for s in suggestions[:4]:
            if s and not any(s.lower().startswith(p) for p in
                    ["strengthen", "quantify", "mirror", "add numbers"]):
                improvements.append({"skill": "Suggestion", "bullet_point": s})
        if not improvements:
            improvements = [
                {"skill": "Keywords",   "bullet_point": "Resume optimized with job description keywords"},
                {"skill": "Formatting", "bullet_point": "ATS-compliant formatting applied"},
            ]

        # Step 7: Generate PDF — pass resume_data (not resume_text/task_id/structured)
        pdf_buf = generate_optimized_resume(
            filename=file.filename,
            score=round(ats_score, 1),
            improvements=improvements,
            resume_data=resume_data,
        )
        pdf_buf.seek(0)
        pdf_bytes = pdf_buf.read()
        return analysis, pdf_bytes, resume_text

    try:
        analysis, pdf_bytes, resume_text = await run_in_threadpool(run_analysis)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    # Save to DB
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

    # Save to filesystem (local dev)
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
            "id":               task_id,
            "task_id":          task_id,
            "resume_id":        task_id,
            "overall_score":    analysis.get("overall_score", 0),
            "ats_score":        analysis.get("overall_score", 0),
            "keywords_matched": analysis.get("keywords_matched", 0),
            "keywords_missing": analysis.get("keywords_missing", 0),
            "total_keywords":   analysis.get("total_keywords", 0),
            "missing_list":     analysis.get("missing_list", []),
            "breakdown":        analysis.get("breakdown", {}),
            "suggestions":      analysis.get("suggestions", []),
            "job_title":        job_title,
            "status":           "success"
        }
    }


@router.get("/preview/{resume_id}")
def get_resume_preview(
    resume_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    resume = db.query(Resume).filter(
        Resume.filename == f"optimized_{resume_id}.pdf"
    ).order_by(Resume.id.desc()).first()

    if not resume:
        raise HTTPException(status_code=404, detail="Resume preview not found.")

    return {
        "resume_id":     resume_id,
        "filename":      resume.filename,
        "ats_score":     resume.ats_score,
        "analysis_data": resume.analysis_data,
        "status":        "completed",
    }


@router.get("/status/{task_id}")
def get_resume_status(task_id: str, db: Session = Depends(get_db)):
    resume = db.query(Resume).filter(
        Resume.filename == f"optimized_{task_id}.pdf"
    ).first()
    if resume:
        return {"task_id": task_id, "status": "completed", "result": resume.analysis_data}
    return {"task_id": task_id, "status": "pending", "result": None}


@router.get("/download/{task_id}")
async def download_resume(task_id: str, db: Session = Depends(get_db)):
    # Try filesystem first (local dev)
    file_path = os.path.join(OUTPUT_DIR, f"optimized_{task_id}.pdf")
    if os.path.exists(file_path):
        return FileResponse(
            path=file_path,
            media_type="application/pdf",
            filename=f"Resume_{task_id}.pdf"
        )

    # Try database (Railway production)
    resume = db.query(Resume).filter(
        Resume.filename == f"optimized_{task_id}.pdf"
    ).order_by(Resume.id.desc()).first()

    if resume and resume.content:
        return Response(
            content=resume.content,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="Resume_{task_id}.pdf"'}
        )

    raise HTTPException(status_code=404, detail="Resume not found. It may still be generating.")
