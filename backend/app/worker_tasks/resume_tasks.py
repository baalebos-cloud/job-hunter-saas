import os
import tempfile
import logging
from backend.app.celery_app import celery_app
from backend.app.utils.pdf_generator import generate_optimized_resume

logger = logging.getLogger(__name__)

# FIX: Unified output directory — must match the download route in resume.py
# resume.py download looks for: /app/output/optimized_{task_id}.pdf
OUTPUT_DIR = "/app/output"


@celery_app.task(bind=True, name="process_resume_task")
def process_resume_task(self, file_content, original_filename, job_description, user_id, job_title):
    """
    FIX 1: file_content is raw bytes from the upload — the old code treated it
    as a file path and did os.path.exists(file_path) which always failed.
    We now write the bytes to a temp file first before any processing.

    FIX 2: Output path now matches resume.py download route:
    /app/output/optimized_{task_id}.pdf
    """
    task_id = self.request.id
    logger.info(f"--- STARTING TASK {task_id} ---")

    # Write bytes to a real temp file so any file-reading tools can access it
    tmp_path = None
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # FIX: Write the raw bytes to disk as a named temp file
        suffix = os.path.splitext(original_filename)[-1] or ".pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name

        logger.info(f"Resume written to temp file: {tmp_path}")

        # --- ANALYSIS LOGIC ---
        # TODO: Replace hardcoded score with real ATS engine call using tmp_path
        ats_score = 17.49
        suggestions = [
            "Consider adding more action verbs.",
            "Consider adding more certifications.",
            "Consider adding more education.",
            "Consider adding more soft skills."
        ]
        tech_skills = ["Cloud Computing"]

        # --- GENERATE PDF ---
        # FIX: generate_optimized_resume must save to OUTPUT_DIR/optimized_{task_id}.pdf
        # to match the download route. Pass task_id so it can name the file correctly.
        logger.info(f"Generating PDF for task {task_id}")
        generate_optimized_resume(
            filename=original_filename,
            score=ats_score,
            improvements=[{"skill": "General", "bullet_point": s} for s in suggestions],
            task_id=task_id
        )

        # --- VERIFY OUTPUT ---
        expected_pdf = os.path.join(OUTPUT_DIR, f"optimized_{task_id}.pdf")
        if os.path.exists(expected_pdf):
            logger.info(f"SUCCESS: PDF created at {expected_pdf}")
        else:
            logger.error(f"CRITICAL: PDF generator ran but {expected_pdf} is missing!")

        return {
            "id": task_id,
            "task_id": task_id,
            "resume_id": task_id,
            "ats_score": ats_score,
            "overall_score": ats_score,
            "keywords_matched": 2,
            "keywords_missing": 8,
            "total_keywords": 10,
            "missing_list": suggestions,
            "improvement_suggestions": suggestions,
            "breakdown": {
                "action_verbs": {"score": 20, "count": 1},
                "technical_skills": {"score": 15, "count": 1},
                "soft_skills": {"score": 10, "count": 0}
            },
            "highlights": {
                "technical": tech_skills,
                "action_verbs": [],
                "certifications": [],
                "education": [],
                "soft_skills": []
            },
            "job_title": job_title or "Target Role",
            "status": "success"
        }

    except Exception as e:
        logger.error(f"FATAL WORKER ERROR for task {task_id}: {str(e)}", exc_info=True)
        raise e

    finally:
        # Always clean up the temp file
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
            logger.info(f"Temp file cleaned up: {tmp_path}")