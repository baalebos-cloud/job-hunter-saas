"""Daily data-retention job (GDPR storage limitation / SOC 2 retention)."""
import logging

from backend.app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="backend.app.tasks.maintenance.run_retention")
def run_retention():
    from backend.app.database import SessionLocal
    from backend.app.services.audit import record_event
    from backend.app.services.privacy import run_retention as purge
    db = SessionLocal()
    try:
        result = purge(db)
    finally:
        db.close()
    record_event("privacy.retention_run", details=result)
    logger.info("retention_run %s", result)
    return result
