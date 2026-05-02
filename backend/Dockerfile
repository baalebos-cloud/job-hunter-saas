FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY start.sh ./start.sh
COPY start-worker.sh ./start-worker.sh
COPY start-beat.sh ./start-beat.sh

RUN mkdir -p /app/output /app/uploads && \
    chmod +x /app/start.sh /app/start-worker.sh /app/start-beat.sh

RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

CMD ["/app/start.sh"]
