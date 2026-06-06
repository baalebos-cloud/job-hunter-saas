#!/bin/sh
# Baalebos Cloud — Smart Start Script
# Set SERVICE_TYPE in Railway Variables to control what runs:
#   SERVICE_TYPE=api     → runs FastAPI (default)
#   SERVICE_TYPE=worker  → runs keep-alive (no Redis needed)
#   SERVICE_TYPE=beat    → runs keep-alive (cron-job.org handles scraping)

SERVICE_TYPE="${SERVICE_TYPE:-api}"

echo "Starting Baalebos Cloud service: $SERVICE_TYPE"

case "$SERVICE_TYPE" in
  worker|beat)
    echo "Worker/Beat: Analysis runs directly in API. Standby mode."
    while true; do
      sleep 3600
    done
    ;;
  *)
    exec uvicorn backend.app.main:app \
      --host 0.0.0.0 \
      --port "${PORT:-8000}" \
      --proxy-headers \
      --forwarded-allow-ips "*"
    ;;
esac
