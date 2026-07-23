FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN set -eux; \
    apt-get update --fix-missing -y && \
    apt-get install -y --no-install-recommends \
        libpq-dev \
        build-essential \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . ./backend

RUN printf '#!/bin/bash\nset -e\nexec uvicorn backend.app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips "*"\n' > /app/start.sh && \
    printf '#!/bin/bash\nset -e\nexec celery -A backend.app.celery_app worker --loglevel=info --concurrency=2\n' > /app/start-worker.sh && \
    printf '#!/bin/bash\nset -e\nsleep 5\nexec celery -A backend.app.celery_app beat --loglevel=info --schedule=/tmp/celerybeat-schedule\n' > /app/start-beat.sh && \
    chmod +x /app/start.sh /app/start-worker.sh /app/start-beat.sh

RUN test -f /app/backend/app/main.py || (echo "ERROR: main.py missing!" && exit 1)

RUN mkdir -p /app/output /app/uploads

RUN useradd -m appuser && chown -R appuser:appuser /app

USER appuser

CMD ["/app/start.sh"]
