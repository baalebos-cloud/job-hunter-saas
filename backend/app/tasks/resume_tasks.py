import os
import logging
from backend.app.celery_app import celery_app
from backend.app.utils.pdf_generator import generate_optimized_resume
from backend.app.utils.ats_engine import analyze_detailed_ats

logger = logging.getLogger(__name__)

OUTPUT_DIR = "/app/output"


@celery_app.task(bind=True, name="process_resume_task")
def process_resume_task(self, file_content, original_filename, job_description, user_id, job_title):
    """
    1. Run real ATS analysis via OpenRouter
    2. Generate optimized PDF
    3. Return structured result to frontend
    """
    task_id = self.request.id
    logger.info(f"--- STARTING TASK {task_id} for {original_filename} ---")

    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # ── Step 1: Real AI Analysis ─────────────────────────────────────────
        logger.info(f"Running ATS analysis for task {task_id}")
        analysis = analyze_detailed_ats(
            file_content=bytes(file_content) if not isinstance(file_content, bytes) else file_content,
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

        # ── Step 2: Build improvements for PDF ───────────────────────────────
        improvements = []

        # Use AI suggestions if available
        for s in suggestions[:4]:
            improvements.append({"skill": "Improvement", "bullet_point": s})

        # Pad with missing keywords if suggestions are few
        for kw in missing_list[:4]:
            if len(improvements) >= 8:
                break
            improvements.append({
                "skill": kw,
                "bullet_point": f"Incorporate '{kw}' into your resume to improve ATS matching."
            })

        # Fallback if nothing
        if not improvements:
            improvements = [
                {"skill": "Action Verbs", "bullet_point": "Use stronger action verbs to improve impact."},
                {"skill": "Keywords", "bullet_point": "Mirror job description keywords throughout your resume."},
            ]

        # ── Step 3: Generate PDF ─────────────────────────────────────────────
        logger.info(f"Generating PDF for task {task_id}")
        pdf_buffer = generate_optimized_resume(
            filename=original_filename,
            score=round(ats_score, 1),
            improvements=improvements
        )

        # Save to shared output volume
        output_path = os.path.join(OUTPUT_DIR, f"optimized_{task_id}.pdf")
        with open(output_path, "wb") as f:
            f.write(pdf_buffer.read())

        if os.path.exists(output_path):
            logger.info(f"SUCCESS: PDF saved at {output_path}")
        else:
            logger.error(f"PDF file missing after write: {output_path}")

        # ── Step 4: Return structured result ─────────────────────────────────
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