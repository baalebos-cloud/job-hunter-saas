#!/bin/bash
set -e

echo "Starting Celery Worker..."
exec celery -A backend.app.celery_app worker \
    --loglevel=info \
    --concurrency=2
