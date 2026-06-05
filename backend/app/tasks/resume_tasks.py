import os
import logging
from backend.app.celery_app import celery_app
from backend.app.utils.pdf_generator import generate_optimized_resume
from backend.app.utils.ats_engine import analyze_detailed_ats, extract_resume_data

logger = logging.getLogger(__name__)
OUTPUT_DIR = "/app/output"


@celery_app.task(bind=True, name="process_resume_task")
def process_resume_task(self, file_content, original_filename, job_description, user_id, job_title):
    task_id = self.request.id
    logger.info(f"--- STARTING TASK {task_id} for {original_filename} ---")

    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        if not isinstance(file_content, bytes):
            file_content = bytes(file_content)

        # Step 1: ATS Scoring
        logger.info(f"[{task_id}] Running ATS analysis...")
        analysis = analyze_detailed_ats(file_content, original_filename, job_description)
        ats_score    = analysis.get("overall_score", 0)
        missing_list = analysis.get("missing_list", [])
        breakdown    = analysis.get("breakdown", {
            "action_verbs":     {"score": 0, "count": 0},
            "technical_skills": {"score": 0, "count": 0},
            "soft_skills":      {"score": 0, "count": 0}
        })
        suggestions = analysis.get("suggestions", [])
        logger.info(f"[{task_id}] ATS Score: {ats_score}%")

        # Step 2: Extract Resume Structure
        logger.info(f"[{task_id}] Extracting resume structure...")
        resume_data = extract_resume_data(file_content, original_filename, job_title)
        resume_data["missing_keywords"] = missing_list

        # Step 3: Build improvement bullets
        improvements = []
        for s in suggestions[:4]:
            improvements.append({"skill": "AI Suggestion", "bullet_point": s})
        for kw in missing_list[:4]:
            if len(improvements) >= 8:
                break
            if kw and "API Key" not in kw:
                improvements.append({
                    "skill": kw,
                    "bullet_point": f"Incorporate '{kw}' naturally into your experience bullets to improve ATS matching."
                })
        if not improvements:
            improvements = [
                {"skill": "Action Verbs", "bullet_point": "Use stronger action verbs like Architected, Spearheaded, Engineered."},
                {"skill": "Metrics", "bullet_point": "Quantify achievements with numbers (e.g. reduced deployment time by 40%)."},
                {"skill": "Keywords", "bullet_point": "Mirror exact keywords from the job description throughout your resume."},
            ]

        # Step 4: Generate Professional PDF
        logger.info(f"[{task_id}] Generating professional PDF...")
        pdf_buffer = generate_optimized_resume(
            filename=original_filename,
            score=round(ats_score, 1),
            improvements=improvements,
            resume_data=resume_data
        )
        output_path = os.path.join(OUTPUT_DIR, f"optimized_{task_id}.pdf")
        with open(output_path, "wb") as f:
            f.write(pdf_buffer.read())

        if os.path.exists(output_path):
            logger.info(f"[{task_id}] SUCCESS: PDF saved at {output_path}")
        else:
            logger.error(f"[{task_id}] PDF missing after write!")

        # Step 5: Return result to frontend
        return {
            "id":               task_id,
            "task_id":          task_id,
            "resume_id":        task_id,
            "overall_score":    ats_score,
            "ats_score":        ats_score,
            "keywords_matched": analysis.get("keywords_matched", 0),
            "keywords_missing": analysis.get("keywords_missing", 0),
            "total_keywords":   analysis.get("total_keywords", 0),
            "missing_list":     missing_list,
            "breakdown":        breakdown,
            "suggestions":      suggestions,
            "job_title":        job_title or "Target Role",
            "status":           "success"
        }

    except Exception as e:
        logger.error(f"[{task_id}] FATAL ERROR: {str(e)}", exc_info=True)
        raise e
