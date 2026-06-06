#!/bin/sh
exec celery -A backend.app.celery_app beat --loglevel=info --schedule=/tmp/celerybeat-schedule
