import logging
from backend.app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="backend.app.tasks.scrape_jobs")
def scrape_jobs():
    """Runs every 5 minutes via Celery beat to keep jobs fresh."""
    try:
        from backend.app.utils.global_scraper import scrape_global_jobs
        result = scrape_global_jobs()
        logger.info(f"[Beat] Scrape complete: {result}")
        return result
    except Exception as e:
        logger.error(f"[Beat] Scrape failed: {e}", exc_info=True)
        raise
