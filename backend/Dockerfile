FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Add Acquire::Retries to prevent Debian mirror timeout errors
RUN apt-get update -o Acquire::Retries=3 -y && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy ALL source files from backend/ into /app
COPY . .

# Since start scripts live in backend/, COPY . . already copied them!
# We just need to ensure they have execution permissions.

# Corrected path checks (relative to /app when building from backend context)
RUN test -f /app/app/routes/admin.py || (echo "ERROR: admin.py missing!" && exit 1)
RUN test -f /app/app/routes/hr.py || (echo "ERROR: hr.py missing!" && exit 1)
RUN test -f /app/app/main.py || (echo "ERROR: main.py missing!" && exit 1)

RUN mkdir -p /app/output /app/uploads && \
    chmod +x /app/start.sh /app/start-worker.sh /app/start-beat.sh

RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

CMD ["/app/start.sh"]
