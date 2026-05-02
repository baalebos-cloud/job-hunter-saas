import os
from celery import Celery
from celery.schedules import crontab
from backend.app.core.config import settings

redis_url = settings.REDIS_URL

# Upstash uses rediss:// (SSL). Celery's redis transport needs the URL
# as redis:// but with SSL options passed separately.
broker_use_ssl = None
redis_backend_use_ssl = None
broker_url = redis_url
backend_url = redis_url

if redis_url.startswith("rediss://"):
    ssl_opts = {
        "ssl_cert_reqs": "none",
        "ssl_ca_certs": None,
        "ssl_certfile": None,
        "ssl_keyfile": None,
    }
    broker_use_ssl = ssl_opts
    redis_backend_use_ssl = ssl_opts
    # Celery needs redis:// not rediss:// — SSL passed via broker_use_ssl
    broker_url = redis_url.replace("rediss://", "redis://", 1)
    backend_url = redis_url.replace("rediss://", "redis://", 1)

celery_app = Celery(
    "job_hunter",
    broker=broker_url,
    backend=backend_url
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    broker_use_ssl=broker_use_ssl,
    redis_backend_use_ssl=redis_backend_use_ssl,
    broker_transport_options={'visibility_timeout': 3600},
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
    'backend.app.tasks.resume_tasks',
    'backend.app.tasks.application_tasks',
])

if __name__ == "__main__":
    celery_app.start()
