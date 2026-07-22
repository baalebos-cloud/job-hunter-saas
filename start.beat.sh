#!/bin/bash
set -e
echo "Starting Celery Beat Scheduler..."
exec celery -A backend.app.celery_app beat --loglevel=info
