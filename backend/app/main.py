import io
import os
import time
from collections import defaultdict
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.app.database import Base, engine, get_db
from backend.app.routes import jobs, resume, auth, application, dashboard
from backend.app.routes import admin as admin_router
from backend.app.routes import hr as hr_router
from backend.app.services.ai_service import ai_engine

from backend.app.models.user import User, OutreachMessage  # noqa: F401
from backend.app.models.job import Job  # noqa: F401
from backend.app.models.resume import Resume  # noqa: F401
from backend.app.models.application import Application  # noqa: F401

app = FastAPI(
    title="Baalebos Cloud AI v2",
    # Hide API docs in production
    docs_url=None if os.getenv("ENVIRONMENT") == "production" else "/docs",
    redoc_url=None if os.getenv("ENVIRONMENT") == "production" else "/redoc",
    openapi_url=None if os.getenv("ENVIRONMENT") == "production" else "/openapi.json",
)

# ── Rate limiting (in-memory) ─────────────────────────────────────────────────
# Tracks: {ip: [(timestamp, count)]}
_rate_store: dict = defaultdict(list)

RATE_LIMITS = {
    "/api/v1/auth/login":  (10, 60),   # 10 requests per 60 seconds
    "/api/v1/auth/signup": (5,  60),   # 5 requests per 60 seconds
    "/api/v1/resume":      (20, 60),   # 20 requests per 60 seconds
    "default":             (100, 60),  # 100 requests per 60 seconds
}


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    ip = _get_client_ip(request)
    path = request.url.path
    now = time.time()

    # Find matching rate limit rule
    limit, window = RATE_LIMITS.get("default")
    for route_prefix, (lim, win) in RATE_LIMITS.items():
        if route_prefix != "default" and path.startswith(route_prefix):
            limit, window = lim, win
            break

    key = f"{ip}:{path}"
    # Clean old entries
    _rate_store[key] = [t for t in _rate_store[key] if now - t < window]
    if len(_rate_store[key]) >= limit:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please slow down."},
            headers={"Retry-After": str(window)}
        )
    _rate_store[key].append(now)
    return await call_next(request)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if os.getenv("ENVIRONMENT") == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.on_event("startup")
async def startup_event():
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created/verified")
        # Add new columns if they don't exist (safe migration)
        from sqlalchemy import text
        with engine.connect() as conn:
            migrations = [
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_hr BOOLEAN DEFAULT FALSE",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS company_name VARCHAR",
                "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS posted_by_hr BOOLEAN DEFAULT FALSE",
                "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS hr_user_id INTEGER",
            ]
            for sql in migrations:
                try:
                    conn.execute(text(sql))
                    conn.commit()
                except Exception:
                    pass  # column already exists
        print("✅ DB migrations applied")
    except Exception as e:
        print(f"⚠️ DB startup warning: {e}")

# --- SCHEMAS ---
class AnalysisRequest(BaseModel):
    resume_text: str
    job_description: str

# --- CORS SETUP ---
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
FRONTEND_URL = os.getenv("FRONTEND_URL", "")  # Set in Railway: https://baalebo.xyz

if ENVIRONMENT == "production":
    origins = [
        "https://baalebo.xyz",
        "https://www.baalebo.xyz",
        "https://job-hunter-saas-six.vercel.app",
        "https://job-hunter-saas-production.up.railway.app",
    ]
    if FRONTEND_URL and FRONTEND_URL not in origins:
        origins.append(FRONTEND_URL)
else:
    origins = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ROUTES ---
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["Jobs"])
app.include_router(resume.router, prefix="/api/v1/resume", tags=["Resume"])
app.include_router(application.router, prefix="/api/v1/application", tags=["Application"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
app.include_router(admin_router.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(hr_router.router, prefix="/api/v1/hr", tags=["HR"])

# Admin login is under /api/v1/auth/admin/login (already in auth router)

# --- AI ANALYZE ENDPOINT ---
@app.post("/api/v1/ai/analyze", tags=["AI Engine"])
async def analyze_resume_against_job(payload: AnalysisRequest):
    try:
        result = await ai_engine.analyze_resume(payload.resume_text, payload.job_description)
        return result  
    except Exception as e:
        print(f"Detailed Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
@app.get("/health")
@app.get("/api/v1/health")
async def health_check():
    return {"status": "healthy", "service": "baalebos-cloud"}


@app.post("/api/v1/admin/scrape")
async def trigger_scrape(request: Request):
    """Admin-only scrape trigger — protected by secret key."""
    admin_key = request.headers.get("X-Admin-Key", "")
    expected  = os.getenv("ADMIN_SECRET_KEY", "")
    if not expected or admin_key != expected:
        raise HTTPException(status_code=403, detail="Forbidden")
    from fastapi.concurrency import run_in_threadpool
    from backend.app.utils.global_scraper import scrape_global_jobs
    result = await run_in_threadpool(scrape_global_jobs)
    return result


@app.post("/api/v1/cron/scrape")
@app.get("/api/v1/cron/scrape")
async def cron_scrape(request: Request):
    """Cron-safe endpoint — accepts secret via query param or header for Railway cron."""
    secret = (
        request.headers.get("X-Cron-Secret", "")
        or request.query_params.get("secret", "")
    )
    expected = os.getenv("CRON_SECRET", os.getenv("ADMIN_SECRET_KEY", ""))
    if not expected or secret != expected:
        raise HTTPException(status_code=403, detail="Forbidden")
    from fastapi.concurrency import run_in_threadpool
    from backend.app.utils.global_scraper import scrape_global_jobs
    result = await run_in_threadpool(scrape_global_jobs)
    return result