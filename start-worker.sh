#!/bin/sh
# Worker keep-alive — Celery worker is not needed since analysis runs
# directly in the API on Railway. This prevents Railway from showing
# a crash loop warning on the worker service.
echo "Worker service started. Analysis runs directly in API (no Celery needed)."
while true; do
  sleep 3600
done
