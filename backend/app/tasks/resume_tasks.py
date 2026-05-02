import os
import logging
from backend.app.celery_app import celery_app
from backend.app.utils.pdf_generator import generate_optimized_resume
from backend.app.utils.ats_engine import analyze_detailed_ats, extract_text, rewrite_resume_for_job

logger = logging.getLogger(__name__)

OUTPUT_DIR = "/app/output"


@celery_app.task(bind=True, name="process_resume_task")
def process_resume_task(self, file_content, original_filename, job_description, user_id, job_title):
    task_id = self.request.id
    logger.info(f"--- STARTING TASK {task_id} for {original_filename} ---")

    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        file_bytes = bytes(file_content) if not isinstance(file_content, bytes) else file_content

        # ── Step 1: Extract raw text ──────────────────────────────────────────
        resume_text = extract_text(file_bytes, original_filename)
        logger.info(f"Extracted {len(resume_text)} chars from {original_filename}")

        # ── Step 2: ATS Analysis (scoring + missing keywords) ─────────────────
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

        # ── Step 3: AI Resume Rewrite tailored to the job ─────────────────────
        logger.info(f"Rewriting resume for '{job_title}' with Groq AI")
        structured = rewrite_resume_for_job(
            resume_text=resume_text,
            job_description=job_description,
            job_title=job_title,
            missing_keywords=missing_list
        )

        # ── Step 4: Build improvements list for PDF page 2 ────────────────────
        improvements = []
        for s in suggestions[:5]:
            improvements.append({"skill": "AI Suggestion", "bullet_point": s})
        for kw in missing_list[:5]:
            if len(improvements) >= 10:
                break
            improvements.append({
                "skill": kw,
                "bullet_point": f"Incorporate '{kw}' naturally into your experience bullets and skills section — this keyword is in the job description and boosts your ATS score."
            })
        if not improvements:
            improvements = [
                {"skill": "Action Verbs", "bullet_point": "Start every bullet with a strong action verb: Architected, Engineered, Spearheaded, Optimized, Automated."},
                {"skill": "Quantify Impact", "bullet_point": "Add numbers to achievements: 'Reduced deployment time by 40%', 'Managed infrastructure for 500K+ users'."},
            ]

        # ── Step 5: Generate full professional PDF ────────────────────────────
        logger.info(f"Generating professional PDF for task {task_id}")
        pdf_buffer = generate_optimized_resume(
            filename=original_filename,
            score=round(ats_score, 1),
            improvements=improvements,
            resume_text=resume_text,
            task_id=task_id,
            structured=structured,       # ← AI-rewritten structured resume
        )

        output_path = os.path.join(OUTPUT_DIR, f"optimized_{task_id}.pdf")
        with open(output_path, "wb") as f:
            f.write(pdf_buffer.read())

        if os.path.exists(output_path):
            logger.info(f"SUCCESS: PDF saved at {output_path} ({os.path.getsize(output_path)} bytes)")
        else:
            logger.error(f"PDF missing after write: {output_path}")

        # ── Step 6: Return result to frontend ─────────────────────────────────
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
