FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update -y && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy ALL source files — this layer always rebuilds when any file changes
COPY . .
COPY start.sh ./start.sh
COPY start-worker.sh ./start-worker.sh
COPY start-beat.sh ./start-beat.sh

# Verify critical files exist at build time — fails build if missing
RUN test -f /app/backend/app/routes/admin.py || (echo "ERROR: admin.py missing!" && exit 1)
RUN test -f /app/backend/app/routes/hr.py || (echo "ERROR: hr.py missing!" && exit 1)
RUN test -f /app/backend/app/main.py || (echo "ERROR: main.py missing!" && exit 1)

RUN mkdir -p /app/output /app/uploads && \
    chmod +x /app/start.sh /app/start-worker.sh /app/start-beat.sh

RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

CMD ["/app/start.sh"]
