import os
import logging
from backend.app.celery_app import celery_app
from backend.app.utils.pdf_generator import generate_optimized_resume
from backend.app.utils.ats_engine import analyze_detailed_ats, extract_text, rewrite_resume_for_job

logger = logging.getLogger(__name__)

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/app/output")


@celery_app.task(bind=True, name="process_resume_task")
def process_resume_task(self, file_content, original_filename, job_description, user_id, job_title):
    task_id = self.request.id
    logger.info(f"--- STARTING TASK {task_id} for {original_filename} ---")

    try:
        file_bytes = bytes(file_content) if not isinstance(file_content, bytes) else file_content

        # ── Step 1: Extract raw text ──────────────────────────────────────────
        resume_text = extract_text(file_bytes, original_filename)
        logger.info(f"Extracted {len(resume_text)} chars from {original_filename}")

        # ── Step 2: ATS Analysis ──────────────────────────────────────────────
        logger.info(f"Running Groq ATS analysis for task {task_id}")
        analysis = analyze_detailed_ats(
            file_content=file_bytes,
            filename=original_filename,
            job_description=job_description
        )

        ats_score    = analysis.get("overall_score", 0)
        missing_list = analysis.get("missing_list", [])
        breakdown    = analysis.get("breakdown", {
            "action_verbs":     {"score": 0, "count": 0},
            "technical_skills": {"score": 0, "count": 0},
            "soft_skills":      {"score": 0, "count": 0},
        })
        suggestions = analysis.get("suggestions", [])
        logger.info(f"ATS Score: {ats_score}% | Missing: {len(missing_list)} keywords")

        # ── Step 3: AI Resume Rewrite ─────────────────────────────────────────
        logger.info(f"Rewriting resume for '{job_title}' with Groq AI")
        structured = rewrite_resume_for_job(
            resume_text=resume_text,
            job_description=job_description,
            job_title=job_title,
            missing_keywords=missing_list
        )

        # ── Step 4: Build improvements list ──────────────────────────────────
        improvements = []
        for s in suggestions[:5]:
            improvements.append({"skill": "AI Suggestion", "bullet_point": s})
        for kw in missing_list[:5]:
            if len(improvements) >= 10:
                break
            improvements.append({
                "skill": kw,
                "bullet_point": f"Incorporate '{kw}' naturally into your experience bullets and skills section."
            })
        if not improvements:
            improvements = [
                {"skill": "Action Verbs", "bullet_point": "Start every bullet with a strong action verb: Architected, Engineered, Spearheaded, Optimized, Automated."},
                {"skill": "Quantify Impact", "bullet_point": "Add numbers to achievements: 'Reduced deployment time by 40%', 'Managed infrastructure for 500K+ users'."},
            ]

        # ── Step 5: Generate PDF ──────────────────────────────────────────────
        logger.info(f"Generating professional PDF for task {task_id}")
        pdf_buffer = generate_optimized_resume(
            filename=original_filename,
            score=round(ats_score, 1),
            improvements=improvements,
            resume_text=resume_text,
            task_id=task_id,
            structured=structured,
        )
        pdf_bytes = pdf_buffer.read()

        # ── Step 6: Save PDF to PostgreSQL (Railway-safe) ─────────────────────
        try:
            from backend.app.database import SessionLocal
            from backend.app.models.resume import Resume
            db_session = SessionLocal()
            resume_record = Resume(
                owner_id=user_id,
                filename=f"optimized_{task_id}.pdf",
                content=pdf_bytes,
                ats_score=ats_score,
                analysis_data={
                    "task_id": task_id,
                    "job_title": job_title,
                    "overall_score": ats_score,
                    "missing_list": missing_list,
                    "suggestions": suggestions,
                }
            )
            db_session.add(resume_record)
            db_session.commit()
            db_session.close()
            logger.info(f"PDF saved to database for task {task_id}")
        except Exception as db_err:
            logger.warning(f"Could not save PDF to DB: {db_err}")

        # ── Step 7: Also save to filesystem (local dev fallback) ──────────────
        try:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            output_path = os.path.join(OUTPUT_DIR, f"optimized_{task_id}.pdf")
            with open(output_path, "wb") as f:
                f.write(pdf_bytes)
            logger.info(f"PDF saved to filesystem: {output_path}")
        except Exception as fs_err:
            logger.warning(f"Could not save PDF to filesystem: {fs_err}")

        # ── Step 8: Return result to frontend ─────────────────────────────────
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
