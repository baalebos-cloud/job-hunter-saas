#!/bin/bash
set -e

echo "Starting Celery Beat Scheduler..."

# Wait for the main app/broker to be ready (optional: adjust sleep or use wait-for-it)
sleep 5

exec celery -A backend.app.celery_app beat \
    --loglevel=info \
    --scheduler django_celery_beat.schedulers:DatabaseScheduler 2>/dev/null || \
exec celery -A backend.app.celery_app beat \
    --loglevel=info
