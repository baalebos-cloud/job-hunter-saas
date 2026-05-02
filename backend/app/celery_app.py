from celery import Celery
from backend.app.core.config import settings

redis_url = settings.REDIS_URL

celery_app = Celery(
    "job_hunter",
    broker=redis_url,
    backend=redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    broker_transport_options={
        "visibility_timeout": 3600,
        "socket_timeout": 30,
        "socket_connect_timeout": 30,
    },
    # SSL for Upstash rediss:// — let the URL scheme handle SSL automatically
    broker_use_ssl={
        "ssl_cert_reqs": "none"
    } if redis_url.startswith("rediss://") else None,
    redis_backend_use_ssl={
        "ssl_cert_reqs": "none"
    } if redis_url.startswith("rediss://") else None,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    beat_schedule={
        "scrape-jobs-every-5-minutes": {
            "task": "backend.app.tasks.scrape_jobs",
            "schedule": 300.0,
        },
    },
)

celery_app.autodiscover_tasks([
    "backend.app.tasks.resume_tasks",
    "backend.app.tasks.application_tasks",
])

if __name__ == "__main__":
    celery_app.start()
