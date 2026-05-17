import uuid
import os
import json
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import FileResponse, Response, HTMLResponse
from fastapi.concurrency import run_in_threadpool
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
        raise HTTPException(status_code=400, detail="Unsupported file type. Use PDF, DOCX or DOC.")

    file_content = await file.read()
    if len(file_content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 10MB.")

    # Validate magic bytes
    if file_ext == ".pdf" and not file_content.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Invalid PDF file.")
    if file_ext == ".docx" and not file_content.startswith(b"PK\x03\x04"):
        raise HTTPException(status_code=400, detail="Invalid DOCX file.")

    task_id = str(uuid.uuid4())

    def run_analysis():
        from backend.app.utils.ats_engine import analyze_detailed_ats, extract_text, rewrite_resume_for_job
        from backend.app.utils.pdf_generator import generate_optimized_resume

        # Step 1: Extract text
        resume_text = extract_text(file_content, file.filename)

        # Step 2: ATS scoring
        analysis = analyze_detailed_ats(
            file_content=file_content,
            filename=file.filename,
            job_description=job_description
        )
        ats_score    = analysis.get("overall_score", 0)
        missing_list = analysis.get("missing_list", [])
        suggestions  = analysis.get("suggestions", [])

        # Step 3: AI rewrite — pass BOTH missing keywords AND suggestions
        # Filter out phrases that are not actual skills (sentences/descriptions)
        def is_real_skill(kw: str) -> bool:
            kw = kw.strip()
            # Skip if it's a long phrase (not a skill keyword)
            if len(kw) > 40:
                return False
            # Skip if it reads like a sentence
            if any(kw.lower().startswith(p) for p in [
                "experience", "background", "relevant", "knowledge of",
                "familiarity", "understanding", "ability to", "proven",
                "strong", "excellent", "demonstrated"
            ]):
                return False
            return True

        real_skills_to_add = [kw for kw in missing_list if is_real_skill(kw)]
        context_phrases = [kw for kw in missing_list if not is_real_skill(kw)]

        # Build a richer context for Groq — real skills go into skills array,
        # phrases go into bullet points as context
        all_keywords_to_add = real_skills_to_add + [
            s for s in suggestions
            if s and not any(s.lower().startswith(p) for p in
                ["strengthen", "quantify", "mirror", "add numbers", "use strong"])
        ]

        structured = rewrite_resume_for_job(
            resume_text=resume_text,
            job_description=job_description,
            job_title=job_title,
            missing_keywords=all_keywords_to_add[:15],
            context_phrases=context_phrases  # phrases to weave into bullets, not skills
        )

        # Step 4: Generate clean PDF
        pdf_buf = generate_optimized_resume(
            filename=file.filename,
            score=round(ats_score, 1),
            improvements=[],  # no improvements page — clean resume only
            resume_text=resume_text,
            task_id=task_id,
            structured=structured,
        )
        return analysis, pdf_buf.read(), resume_text

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


@router.get("/preview/{resume_id}", response_class=HTMLResponse)
def get_resume_preview(
    resume_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Return a full HTML preview page for an optimized resume by its task/resume ID."""
    resume = db.query(Resume).filter(
        Resume.filename == f"optimized_{resume_id}.pdf"
    ).order_by(Resume.id.desc()).first()

    if not resume:
        raise HTTPException(status_code=404, detail="Resume preview not found.")

    analysis: dict = resume.analysis_data or {}
    ats_score: float = resume.ats_score or 0.0

    # ── Score colour coding ───────────────────────────────────────────────────
    if ats_score >= 75:
        score_colour = "#22c55e"   # green-500
        score_label  = "Strong Match"
        score_ring   = "#16a34a"
    elif ats_score >= 50:
        score_colour = "#eab308"   # yellow-500
        score_label  = "Moderate Match"
        score_ring   = "#ca8a04"
    else:
        score_colour = "#ef4444"   # red-500
        score_label  = "Needs Improvement"
        score_ring   = "#dc2626"

    # ── Analysis breakdown rows ───────────────────────────────────────────────
    breakdown: dict = analysis.get("breakdown", {})
    breakdown_rows_html = ""
    if breakdown:
        for category, value in breakdown.items():
            label = category.replace("_", " ").title()
            try:
                pct = float(value)
            except (TypeError, ValueError):
                pct = 0.0
            bar_colour = "#22c55e" if pct >= 75 else ("#eab308" if pct >= 50 else "#ef4444")
            breakdown_rows_html += f"""
            <tr class="border-b border-gray-700">
              <td class="py-3 pr-6 text-gray-300 font-medium">{label}</td>
              <td class="py-3 pr-6">
                <div class="flex items-center gap-3">
                  <div class="flex-1 bg-gray-700 rounded-full h-2">
                    <div class="h-2 rounded-full" style="width:{min(pct,100):.0f}%;background:{bar_colour};"></div>
                  </div>
                  <span class="text-sm font-semibold" style="color:{bar_colour};">{pct:.0f}%</span>
                </div>
              </td>
            </tr>"""

    # ── Missing keywords pills ────────────────────────────────────────────────
    missing_list: list = analysis.get("missing_list", [])
    missing_pills_html = ""
    if missing_list:
        for kw in missing_list[:20]:
            missing_pills_html += (
                f'<span class="inline-block bg-red-900/50 text-red-300 border border-red-700 '
                f'text-xs font-medium px-3 py-1 rounded-full">{kw}</span>'
            )
    else:
        missing_pills_html = '<span class="text-gray-500 text-sm">None — great coverage!</span>'

    # ── Suggestions list ──────────────────────────────────────────────────────
    suggestions: list = analysis.get("suggestions", [])
    suggestions_html = ""
    if suggestions:
        for s in suggestions[:10]:
            suggestions_html += (
                f'<li class="flex items-start gap-2 text-gray-300 text-sm">'
                f'<span class="mt-1 text-yellow-400 shrink-0">&#9654;</span>{s}</li>'
            )
    else:
        suggestions_html = '<li class="text-gray-500 text-sm">No additional suggestions.</li>'

    # ── Resume content preview ────────────────────────────────────────────────
    parsed_data: str = resume.parsed_data or ""
    resume_content_html = ""
    if parsed_data:
        # Escape HTML entities and preserve line breaks
        escaped = (
            parsed_data
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        resume_content_html = f'<pre class="whitespace-pre-wrap text-gray-300 text-sm leading-relaxed font-mono">{escaped}</pre>'
    else:
        resume_content_html = (
            '<p class="text-gray-500 text-sm italic">'
            "Resume content not available for preview. Download the PDF to view the full document."
            "</p>"
        )

    # ── Stats bar ─────────────────────────────────────────────────────────────
    keywords_matched: int = analysis.get("keywords_matched", 0)
    keywords_missing: int = analysis.get("keywords_missing", 0)
    total_keywords:   int = analysis.get("total_keywords", 0)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Resume Preview — Baalebos AI</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    body {{ background-color: #0f172a; color: #f1f5f9; font-family: 'Inter', system-ui, sans-serif; }}
    .score-ring {{
      width: 120px; height: 120px;
      border-radius: 50%;
      border: 6px solid {score_ring};
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      box-shadow: 0 0 24px {score_colour}55;
    }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 1.5rem; }}
    .btn-primary {{
      display: inline-flex; align-items: center; gap: 0.5rem;
      background: #6366f1; color: #fff; font-weight: 600;
      padding: 0.625rem 1.25rem; border-radius: 8px;
      text-decoration: none; transition: background 0.2s;
    }}
    .btn-primary:hover {{ background: #4f46e5; }}
    .btn-secondary {{
      display: inline-flex; align-items: center; gap: 0.5rem;
      background: #334155; color: #cbd5e1; font-weight: 600;
      padding: 0.625rem 1.25rem; border-radius: 8px;
      text-decoration: none; transition: background 0.2s;
    }}
    .btn-secondary:hover {{ background: #475569; }}
  </style>
</head>
<body class="min-h-screen">

  <!-- Header -->
  <header class="border-b border-gray-700 bg-gray-900/80 backdrop-blur sticky top-0 z-10">
    <div class="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <span class="text-indigo-400 font-bold text-xl tracking-tight">Baalebos AI</span>
        <span class="text-gray-500 text-sm hidden sm:inline">/ Resume Preview</span>
      </div>
      <div class="flex items-center gap-3">
        <a href="javascript:history.back()" class="btn-secondary">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/>
          </svg>
          Back
        </a>
        <a href="/api/v1/resume/download/{resume_id}" class="btn-primary">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5 5-5M12 15V3"/>
          </svg>
          Download PDF
        </a>
      </div>
    </div>
  </header>

  <main class="max-w-5xl mx-auto px-4 py-8 space-y-6">

    <!-- ATS Score Hero -->
    <div class="card flex flex-col sm:flex-row items-center gap-6">
      <div class="score-ring shrink-0">
        <span class="text-3xl font-extrabold" style="color:{score_colour};">{ats_score:.0f}</span>
        <span class="text-xs text-gray-400 mt-0.5">ATS Score</span>
      </div>
      <div class="flex-1 text-center sm:text-left">
        <h1 class="text-2xl font-bold text-white">Resume Analysis</h1>
        <p class="text-sm mt-1 font-semibold" style="color:{score_colour};">{score_label}</p>
        <p class="text-gray-400 text-sm mt-2">
          Your optimised resume has been analysed against the job description.
          Download the PDF below to use it in your application.
        </p>
        <!-- Quick stats -->
        <div class="flex flex-wrap gap-4 mt-4 justify-center sm:justify-start">
          <div class="text-center">
            <p class="text-lg font-bold text-green-400">{keywords_matched}</p>
            <p class="text-xs text-gray-500">Keywords Matched</p>
          </div>
          <div class="text-center">
            <p class="text-lg font-bold text-red-400">{keywords_missing}</p>
            <p class="text-xs text-gray-500">Keywords Missing</p>
          </div>
          <div class="text-center">
            <p class="text-lg font-bold text-indigo-400">{total_keywords}</p>
            <p class="text-xs text-gray-500">Total Keywords</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Score Breakdown -->
    {f'''
    <div class="card">
      <h2 class="text-lg font-semibold text-white mb-4">Score Breakdown</h2>
      <table class="w-full">
        <tbody>
          {breakdown_rows_html}
        </tbody>
      </table>
    </div>
    ''' if breakdown_rows_html else ''}

    <!-- Two-column: Missing Keywords + Suggestions -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">

      <!-- Missing Keywords -->
      <div class="card">
        <h2 class="text-lg font-semibold text-white mb-3">Missing Keywords</h2>
        <div class="flex flex-wrap gap-2">
          {missing_pills_html}
        </div>
      </div>

      <!-- Suggestions -->
      <div class="card">
        <h2 class="text-lg font-semibold text-white mb-3">Improvement Suggestions</h2>
        <ul class="space-y-2">
          {suggestions_html}
        </ul>
      </div>

    </div>

    <!-- Resume Content Preview -->
    <div class="card">
      <h2 class="text-lg font-semibold text-white mb-4">Resume Content Preview</h2>
      <div class="bg-gray-900 rounded-lg p-4 max-h-[600px] overflow-y-auto border border-gray-700">
        {resume_content_html}
      </div>
    </div>

    <!-- Bottom action bar -->
    <div class="flex flex-col sm:flex-row items-center justify-between gap-4 pt-2 pb-8">
      <a href="javascript:history.back()" class="btn-secondary w-full sm:w-auto justify-center">
        <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/>
        </svg>
        Back to Application
      </a>
      <a href="/api/v1/resume/download/{resume_id}" class="btn-primary w-full sm:w-auto justify-center">
        <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5 5-5M12 15V3"/>
        </svg>
        Download Optimised PDF
      </a>
    </div>

  </main>

</body>
</html>"""

    return HTMLResponse(content=html, status_code=200)


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
