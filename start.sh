#!/bin/bash
set -e
echo "Starting Baalebos Cloud API..."
exec uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}
