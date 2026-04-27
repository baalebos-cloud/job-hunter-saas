import os
from celery import Celery
from backend.app.core.config import settings

# Initialize Celery using the UPPERCASE attribute from Pydantic settings
celery_app = Celery(
    "job_hunter",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.conf.update(
    # --- Serialization & Time ---
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # --- AWS ElastiCache / Redis Production Settings ---
    broker_connection_retry_on_startup=True,
    broker_transport_options={
        'visibility_timeout': 3600,  # 1 hour (Crucial for long AI tasks)
    },

    # --- Worker Efficiency ---
    worker_prefetch_multiplier=1,      # Process 1 task at a time (Best for LLM loads)
    worker_max_tasks_per_child=50,     # Prevent memory leaks by recycling workers
    task_acks_late=True,               # Ensure task finishes before removing from queue
    task_reject_on_worker_lost=True    # Re-queue if container crashes mid-task
)

# Discover tasks using the full package path
celery_app.autodiscover_tasks([
    'backend.app.tasks.resume_tasks',
    'backend.app.tasks.application_tasks'
])

if __name__ == "__main__":
    celery_app.start()
