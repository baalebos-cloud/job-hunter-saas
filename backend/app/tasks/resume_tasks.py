import os
import logging
from backend.app.celery_app import celery_app
from backend.app.utils.pdf_generator import generate_optimized_resume
from backend.app.utils.ats_engine import analyze_detailed_ats, extract_text

logger = logging.getLogger(__name__)

OUTPUT_DIR = "/app/output"


@celery_app.task(bind=True, name="process_resume_task")
def process_resume_task(self, file_content, original_filename, job_description, user_id, job_title):
    task_id = self.request.id
    logger.info(f"--- STARTING TASK {task_id} for {original_filename} ---")

    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        file_bytes = bytes(file_content) if not isinstance(file_content, bytes) else file_content

        # ── Step 1: Extract raw text (reused for both AI + PDF) ──────────────
        resume_text = extract_text(file_bytes, original_filename)

        # ── Step 2: Groq AI Analysis ─────────────────────────────────────────
        logger.info(f"Running Groq ATS analysis for task {task_id}")
        analysis = analyze_detailed_ats(
            file_content=file_bytes,
            filename=original_filename,
            job_description=job_description
        )

        ats_score = analysis.get("overall_score", 0)
        missing_list = analysis.get("missing_list", [])
        breakdown = analysis.get("breakdown", {
            "action_verbs": {"score": 0, "count": 0},
            "technical_skills": {"score": 0, "count": 0},
            "soft_skills": {"score": 0, "count": 0}
        })
        suggestions = analysis.get("suggestions", [])
        logger.info(f"ATS Score for task {task_id}: {ats_score}%")

        # ── Step 3: Build improvements list for PDF page 2 ───────────────────
        improvements = []
        for s in suggestions[:5]:
            improvements.append({"skill": "AI Suggestion", "bullet_point": s})
        for kw in missing_list[:5]:
            if len(improvements) >= 10:
                break
            improvements.append({
                "skill": kw,
                "bullet_point": f"Add '{kw}' to your resume — this keyword appears in the job description and is currently missing from your resume."
            })
        if not improvements:
            improvements = [
                {"skill": "Action Verbs", "bullet_point": "Use stronger action verbs like Architected, Engineered, Spearheaded to improve impact."},
                {"skill": "Keywords", "bullet_point": "Mirror the exact keywords from the job description throughout your resume."},
            ]

        # ── Step 4: Generate full PDF (resume + improvements) ────────────────
        logger.info(f"Generating full PDF for task {task_id}")
        pdf_buffer = generate_optimized_resume(
            filename=original_filename,
            score=round(ats_score, 1),
            improvements=improvements,
            resume_text=resume_text,   # ← full resume on page 1
            task_id=task_id
        )

        output_path = os.path.join(OUTPUT_DIR, f"optimized_{task_id}.pdf")
        with open(output_path, "wb") as f:
            f.write(pdf_buffer.read())

        if os.path.exists(output_path):
            logger.info(f"SUCCESS: PDF saved at {output_path}")
        else:
            logger.error(f"PDF file missing after write: {output_path}")

        # ── Step 5: Return structured result to frontend ──────────────────────
        return {
            "id": task_id,
            "task_id": task_id,
            "resume_id": task_id,
            "overall_score": ats_score,
            "ats_score": ats_score,
            "keywords_matched": analysis.get("keywords_matched", 0),
            "keywords_missing": analysis.get("keywords_missing", 0),
            "total_keywords": analysis.get("total_keywords", 0),
            "missing_list": missing_list,
            "breakdown": breakdown,
            "suggestions": suggestions,
            "job_title": job_title or "Target Role",
            "status": "success"
        }

    except Exception as e:
        logger.error(f"FATAL WORKER ERROR for task {task_id}: {str(e)}", exc_info=True)
        raise e
