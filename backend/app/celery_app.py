# =============================================================================
# backend/app/celery_app.py
# =============================================================================
from celery import Celery
from backend.app.core.config import settings

celery_app = Celery(
    "job_hunter",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    broker_transport_options={"visibility_timeout": 3600},
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    beat_schedule={
        # Scrape jobs every 6 hours — 5 mins was too aggressive for free-tier Railway
        "scrape-jobs-every-6-hours": {
            "task": "backend.app.tasks.scrape_task.scrape_jobs",
            "schedule": 21600.0,  # 6 hours
        },
    },
)

celery_app.autodiscover_tasks([
    "backend.app.tasks.scrape_task",
    "backend.app.tasks.resume_tasks",
    "backend.app.tasks.application_tasks",
])

if __name__ == "__main__":
    celery_app.start()
