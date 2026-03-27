# 1. Use a specific digest or version for reproducibility
FROM python:3.12-slim

# 2. Set Python-specific environment variables for Docker
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# 3. Optimize Layer Caching: Install system dependencies first
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 4. Install Python dependencies before copying code
# This prevents re-installing everything every time you change a line of code
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 5. Copy the project
COPY backend/ ./backend/

# 6. SECURITY: Don't run as root! 
# Create a non-privileged user to run the app
RUN useradd -m myuser
USER myuser

# 7. Use JSON syntax for CMD to handle OS signals (like SIGTERM) correctly
# Use a worker class like 'uvloop' for high performance (standard in production)
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
