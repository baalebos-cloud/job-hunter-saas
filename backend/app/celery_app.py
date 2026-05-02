from celery import Celery
from celery.schedules import crontab
from backend.app.core.config import settings

redis_url = settings.REDIS_URL

# Upstash requires SSL. Celery's redis transport only accepts redis://
# SSL is enabled via broker_use_ssl and redis_backend_use_ssl options.
# We must convert rediss:// → redis:// and pass SSL config separately.
if redis_url.startswith("rediss://"):
    broker_url  = redis_url.replace("rediss://", "redis://", 1)
    backend_url = redis_url.replace("rediss://", "redis://", 1)
    ssl_config  = {"ssl_cert_reqs": "none"}
else:
    broker_url  = redis_url
    backend_url = redis_url
    ssl_config  = None

celery_app = Celery(
    "job_hunter",
    broker=broker_url,
    backend=backend_url,
)

conf = {
    "task_serializer": "json",
    "accept_content": ["json"],
    "result_serializer": "json",
    "timezone": "UTC",
    "enable_utc": True,
    "broker_connection_retry_on_startup": True,
    "broker_transport_options": {"visibility_timeout": 3600},
    "worker_prefetch_multiplier": 1,
    "worker_max_tasks_per_child": 50,
    "task_acks_late": True,
    "task_reject_on_worker_lost": True,
    "beat_schedule": {
        "scrape-jobs-every-5-minutes": {
            "task": "backend.app.tasks.scrape_jobs",
            "schedule": 300.0,
        },
    },
}

if ssl_config:
    conf["broker_use_ssl"] = ssl_config
    conf["redis_backend_use_ssl"] = ssl_config

celery_app.conf.update(conf)

celery_app.autodiscover_tasks([
    "backend.app.tasks.resume_tasks",
    "backend.app.tasks.application_tasks",
])

if __name__ == "__main__":
    celery_app.start()
