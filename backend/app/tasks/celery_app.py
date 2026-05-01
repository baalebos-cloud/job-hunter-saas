# Re-export the canonical Celery app — do not define a second instance here
from backend.app.celery_app import celery_app
