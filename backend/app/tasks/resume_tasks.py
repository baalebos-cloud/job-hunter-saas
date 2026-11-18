"""Celery worker task for the resume refiner (RESUME_PROCESSING_MODE=async)."""
import base64
import logging

from backend.app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="backend.app.tasks.resume_tasks.process_resume_upload", bind=True,
                 acks_late=True, max_retries=0, soft_time_limit=600, time_limit=660)
def process_resume_upload(self, task_id, user_id, content_b64, filename, job_description, job_title, region):
    from backend.app.database import SessionLocal
    from backend.app.models.resume import Resume
    from backend.app.services.resume_pipeline import PipelineFailure, complete_record, run_pipeline
    db = SessionLocal()
    try:
        record = db.query(Resume).filter(Resume.filename == f"optimized_{task_id}.pdf",
                                         Resume.owner_id == user_id).first()
        if record is None or record.status != "processing":
            return {"task_id": task_id, "status": "skipped"}  # deleted, expired or already handled
        try:
            tailored, analysis, pdf = run_pipeline(base64.b64decode(content_b64), filename, job_description,
                                                   job_title, region, task_id)
            complete_record(db, record, tailored, analysis, pdf)
            return {"task_id": task_id, "status": "completed"}
        except PipelineFailure as exc:
            message = exc.message
        except Exception as exc:  # quota race, storage or DB failure
            db.rollback()
            logger.error("resume_worker_failed reference=%s error_type=%s", task_id, type(exc).__name__)
            detail = getattr(exc, "detail", None)
            message = detail if isinstance(detail, str) else f"Resume preparation failed. Nothing was charged; please retry. Reference: {task_id}"
        record = db.query(Resume).filter(Resume.filename == f"optimized_{task_id}.pdf").first()
        if record is not None:
            record.status, record.error = "failed", message[:500]
            db.commit()
        return {"task_id": task_id, "status": "failed"}
    finally:
        db.close()
