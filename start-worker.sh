#!/bin/sh
exec celery -A backend.app.celery_app worker --loglevel=info --concurrency=2
