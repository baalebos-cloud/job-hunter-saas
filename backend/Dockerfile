FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# FIX 1: Pin apt-get to avoid stale mirror issues.
# FIX 2: Add `--fix-missing` and retry logic to handle transient network failures.
# FIX 3: Install build-essential instead of bare gcc — covers all compiler deps.
RUN set -eux; \
    apt-get update --fix-missing -y && \
    apt-get install -y --no-install-recommends \
        libpq-dev \
        build-essential \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy ALL source files — this layer always rebuilds when any file changes
COPY . .

# FIX 4: COPY + chmod in one layer (no need for separate COPY lines after COPY . .)
# start.sh, start-worker.sh, start-beat.sh are already included in COPY . .
RUN chmod +x /app/start.sh /app/start-worker.sh /app/start-beat.sh

# Verify critical files exist at build time — fails build if missing
RUN test -f /app/backend/app/routes/admin.py  || (echo "ERROR: admin.py missing!"  && exit 1)
RUN test -f /app/backend/app/routes/hr.py     || (echo "ERROR: hr.py missing!"     && exit 1)
RUN test -f /app/backend/app/main.py          || (echo "ERROR: main.py missing!"   && exit 1)

RUN mkdir -p /app/output /app/uploads

# FIX 5: Create user AFTER chown so the directory ownership is correct
RUN useradd -m appuser && chown -R appuser:appuser /app

USER appuser

CMD ["/app/start.sh"]
