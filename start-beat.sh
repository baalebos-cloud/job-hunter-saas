#!/bin/bash
set -e

echo "Starting Celery Beat Scheduler..."

# Give the broker (Redis) a moment to be ready
sleep 5

# Use plain beat scheduler — django_celery_beat is not installed
exec celery -A backend.app.celery_app beat \
    --loglevel=info \
    --schedule=/tmp/celerybeat-schedule
