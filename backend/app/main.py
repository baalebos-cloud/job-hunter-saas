import io
import logging
from contextlib import asynccontextmanager
import re
import os
import time
import uuid
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
from backend.app.routes import billing as billing_router
from backend.app.routes import referral as referral_router
from backend.app.routes import hr_auth as hr_auth_router
from backend.app.routes import profile as profile_router
from backend.app.routes import automation as automation_router
from backend.app.routes import rbac as rbac_router
from backend.app.routes import privacy as privacy_router
from backend.app.routes import support as support_router
from backend.app.routes import team as team_router
from backend.app.routes import public_api as public_api_router
from backend.app.routes import governance as governance_router
from backend.app.services.ai_service import ai_engine

from backend.app.models.user import User, OutreachMessage  # noqa: F401
from backend.app.models.job import Job                     # noqa: F401
from backend.app.models.resume import Resume               # noqa: F401
from backend.app.models.application import Application     # noqa: F401
from backend.app.models.subscription import Subscription   # noqa: F401
from backend.app.models.referral import Referral           # noqa: F401
from backend.app.models.automation import AutomationEvent, ScrapeRun, AutomationState  # noqa: F401
from backend.app.models.security import RefreshToken, RbacRole, RbacPermission  # noqa: F401
from backend.app.models.audit import AuditLog, ErasureTombstone  # noqa: F401

logger = logging.getLogger(__name__)

# Secure by default: production protections (hidden API docs, HSTS, strict
# CORS) stay on unless ENVIRONMENT explicitly names a development setting.
# A missing or mistyped variable must never switch them off.
ENVIRONMENT = (os.getenv("ENVIRONMENT") or "production").strip().lower()
IS_DEVELOPMENT = ENVIRONMENT in {"development", "dev", "local", "test"}


def _check_schema_version():
    """No DDL at startup: schema changes run before deploy via
    ``python -m backend.scripts.migrate`` (alembic upgrade head). This only
    reports drift so a missed migration is visible immediately."""
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        from sqlalchemy import text
        from pathlib import Path
        head = ScriptDirectory.from_config(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))).get_current_head()
        with engine.connect() as conn:
            current = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        if current != head:
            logger.error("schema_out_of_date current=%s head=%s - run python -m backend.scripts.migrate", current, head)
    except Exception as exc:
        logger.warning("schema_version_check_skipped error_type=%s", type(exc).__name__)


@asynccontextmanager
async def lifespan(_app):
    _check_schema_version()
    yield


app = FastAPI(
    title="Baalebos Cloud AI v2",
    lifespan=lifespan,
    # API docs only in development
    docs_url="/docs" if IS_DEVELOPMENT else None,
    redoc_url="/redoc" if IS_DEVELOPMENT else None,
    openapi_url="/openapi.json" if IS_DEVELOPMENT else None,
)

# ── Rate limiting (Redis sliding window, trusted-proxy client IP) ────────────
RATE_LIMITS = {
    "/api/v1/auth/login":        (10,  60),   # 10 requests per 60 seconds
    "/api/v1/auth/admin/login":  (10,  60),
    "/api/v1/hr-auth/login":     (10,  60),
    "/api/v1/auth/signup":       (5,   60),   # 5 requests per 60 seconds
    "/api/v1/auth/forgot-password": (5, 300),
    "/api/v1/auth/refresh":      (30,  60),
    # Read-only resume endpoints are owner-scoped; allow 2s status polling
    # (30/min) plus previews. Specific prefixes must precede "/api/v1/resume".
    "/api/v1/resume/status":     (120, 60),
    "/api/v1/resume/preview":    (60,  60),
    "/api/v1/resume/download":   (60,  60),
    "/api/v1/resume":            (20,  60),   # 20 requests per 60 seconds
    "/api/v1/privacy/export":    (5,  3600),
    "/api/v1/governance/summary": (60, 60),
    "/api/v1/billing/webhook":   (200, 60),   # Stripe webhooks — never throttle
    "default":                   (100, 60),   # 100 requests per 60 seconds
}


def _get_client_ip(request: Request) -> str:
    from backend.app.core.client_ip import client_ip
    return client_ip(request)


def reset_rate_limits():
    """Test helper: clear the in-memory fallback store."""
    from backend.app.core.kv_store import memory_store
    memory_store().clear()


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    from backend.app.core.rate_limit import hit
    path = request.url.path
    limit, window = RATE_LIMITS["default"]
    for route_prefix, (lim, win) in RATE_LIMITS.items():
        if route_prefix != "default" and path.startswith(route_prefix):
            limit, window = lim, win
            break
    allowed, retry_after = hit(f"{_get_client_ip(request)}:{path}", limit, window)
    if not allowed:
        return JSONResponse(status_code=429, content={"detail": "Too many requests. Please slow down."},
                            headers={"Retry-After": str(retry_after)})
    return await call_next(request)


def _trace_id(request: Request | None = None) -> str:
    existing = getattr(getattr(request, "state", None), "trace_id", None) if request else None
    return existing or uuid.uuid4().hex


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Opaque 500s: a trace ID for support, details only in server logs."""
    trace_id = _trace_id(request)
    logger.error('unhandled_exception trace_id=%s path=%s error_type=%s', trace_id, request.url.path,
                 type(exc).__name__, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error", "trace_id": trace_id},
                        headers={"X-Trace-Id": trace_id})


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if not IS_DEVELOPMENT:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# ── Observability: trace IDs, metrics, structured audit trail ─────────────────
_PATH_PARAM = re.compile(r"{([^}:]+)(?::[^}]+)?}")


def _route_template(request: Request) -> str:
    """Full route template for metrics and audit, e.g. /api/v1/jobs/board/{job_id}.

    Newer FastAPI versions report only the router-relative path of the matched
    route (e.g. "/me"), so the router prefix is recovered from the real request
    path: the matched route's own part, with its parameters filled in, is the
    tail of the path. Never contains raw parameter values."""
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    if not template:
        return "unmatched"
    params = request.scope.get("path_params") or {}
    try:
        rendered = _PATH_PARAM.sub(lambda m: str(params[m.group(1)]), template)
    except KeyError:
        return template
    path = request.scope.get("path") or ""
    if rendered and path.endswith(rendered):
        return path[: len(path) - len(rendered)] + template
    return template
_TRACE_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")
_UNAUDITED = ("/health", "/metrics", "/api/v1/health")


def _incoming_trace_id(request: Request) -> str:
    traceparent = request.headers.get("traceparent", "")
    parts = traceparent.split("-")
    if len(parts) == 4 and len(parts[1]) == 32 and all(c in "0123456789abcdef" for c in parts[1]):
        return parts[1]
    candidate = request.headers.get("x-request-id", "")
    return candidate.replace("-", "")[:32] if _TRACE_ID.match(candidate) else uuid.uuid4().hex


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    """Outermost middleware: every request (incl. 429s and 500s) gets a trace
    ID, Prometheus metrics, a fleet-wide window sample and an audit record."""
    from backend.app.core import metrics
    from backend.app.services.audit import build_request_entry, emit
    request.state.trace_id = _incoming_trace_id(request)
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Trace-Id"] = request.state.trace_id
        return response
    finally:
        path = request.url.path
        if not path.startswith(_UNAUDITED) and path != "/":
            elapsed = time.perf_counter() - started
            route = _route_template(request)
            metrics.HTTP_REQUESTS.labels(request.method, route, str(status)).inc()
            metrics.HTTP_LATENCY.labels(request.method, route).observe(elapsed)
            if status == 429:
                metrics.RATE_LIMITED.labels(route).inc()
            metrics.record_request(route, status, elapsed * 1000)
            emit(build_request_entry(trace_id=request.state.trace_id, user=getattr(request.state, "actor", None) or getattr(request.state, "user", None),
                                     method=request.method, route=route, status=status,
                                     latency_ms=elapsed * 1000, ip=_get_client_ip(request)))


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics(request: Request, db: Session = Depends(get_db)):
    """Prometheus scrape endpoint: METRICS_TOKEN bearer for scrapers, or a
    signed-in user with metrics:read."""
    import hmac
    from fastapi.responses import Response as RawResponse
    from backend.app.core.metrics import render
    token = os.getenv("METRICS_TOKEN", "")
    supplied = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    allowed = bool(token) and bool(supplied) and hmac.compare_digest(supplied.encode(), token.encode())
    if not allowed and supplied:
        from backend.app.dependencies.auth import decode_access_token
        from backend.app.dependencies.roles import has_permission
        try:
            claims = decode_access_token(supplied)
            user = db.query(User).filter(User.email == claims["sub"]).first()
            allowed = bool(user) and int(claims.get("tv", 0)) == int(user.token_version or 0) \
                and has_permission(db, user, "metrics:read")
        except HTTPException:
            allowed = False
    if not allowed:
        raise HTTPException(status_code=401, detail="Metrics require authorization")
    return RawResponse(render(), media_type="text/plain; version=0.0.4; charset=utf-8")


# --- SCHEMAS ---
class AnalysisRequest(BaseModel):
    resume_text: str
    job_description: str

# --- CORS SETUP ---
FRONTEND_URL = os.getenv("FRONTEND_URL", "")  # Set in Railway: https://baalebo.xyz

if not IS_DEVELOPMENT:
    origins = [
        "https://baalebo.xyz",
        "https://www.baalebo.xyz",
        "https://job-hunter-saas-six.vercel.app",
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
    # Lets the cross-origin dashboard read the candidate-named PDF filename.
    expose_headers=["Content-Disposition"],
)

# --- ROUTES ---
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
from backend.app.routes import job_board as job_board_router
app.include_router(job_board_router.router, prefix="/api/v1/jobs", tags=["Jobs"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["Jobs"])
app.include_router(resume.router, prefix="/api/v1/resume", tags=["Resume"])
app.include_router(application.router, prefix="/api/v1/application", tags=["Application"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
app.include_router(admin_router.router,    prefix="/api/v1/admin",   tags=["Admin"])
app.include_router(hr_router.router,       prefix="/api/v1/hr",      tags=["HR"])
app.include_router(billing_router.router,  prefix="/api/v1/billing",   tags=["Billing"])
app.include_router(referral_router.router, prefix="/api/v1/referral",  tags=["Referral"])
app.include_router(hr_auth_router.router,  prefix="/api/v1/hr-auth",   tags=["HR Auth"])
app.include_router(profile_router.router,  prefix="/api/v1/profile",   tags=["Profile"])
app.include_router(automation_router.router, prefix="/api/v1/automation", tags=["Automation"])
app.include_router(automation_router.alerts_router, prefix="/api/v1/alerts", tags=["Job alerts"])
app.include_router(rbac_router.router, prefix="/api/v1/rbac", tags=["RBAC"])
app.include_router(privacy_router.router, prefix="/api/v1/privacy", tags=["Privacy"])
app.include_router(governance_router.router, prefix="/api/v1/governance", tags=["Governance"])
app.include_router(support_router.router, prefix="/api/v1/support", tags=["Support"])
app.include_router(team_router.router, prefix="/api/v1/team", tags=["Team"])
app.include_router(public_api_router.keys_router, prefix="/api/v1/api-keys", tags=["API keys"])
app.include_router(public_api_router.router, prefix="/api/public/v1", tags=["Integrations API"])

from backend.app.core.telemetry import init_tracing  # noqa: E402
init_tracing(app)

# Admin login is under /api/v1/auth/admin/login (already in auth router)

# --- AI ANALYZE ENDPOINT ---
@app.post("/api/v1/ai/analyze", tags=["AI Engine"])
async def analyze_resume_against_job(payload: AnalysisRequest, current_user=Depends(auth.get_current_user)):
    try:
        return await ai_engine.analyze_resume(payload.resume_text, payload.job_description)
    except Exception as exc:
        # Never echo exception text: it can contain provider or candidate data.
        trace_id = _trace_id()
        logger.error('ai_analyze_failed trace_id=%s error_type=%s', trace_id, type(exc).__name__)
        raise HTTPException(status_code=500, detail=f"Analysis failed. Reference: {trace_id}")

@app.get("/")
@app.get("/health")
@app.get("/api/v1/health")
async def health_check():
    return {"status": "healthy", "service": "baalebos-cloud"}


@app.post("/api/v1/cron/scrape")
@app.get("/api/v1/cron/scrape")
async def cron_scrape(request: Request):
    """Cron-safe endpoint. The secret is accepted only in the X-Cron-Secret
    header (query strings end up in access logs) and compared in constant time."""
    import hmac
    from backend.app.core.config import settings
    supplied = request.headers.get("X-Cron-Secret", "")
    expected = settings.CRON_SECRET or os.getenv("CRON_SECRET", os.getenv("ADMIN_SECRET_KEY", ""))
    if not expected or not supplied or not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(status_code=403, detail="Forbidden")
    from fastapi.concurrency import run_in_threadpool
    from backend.app.utils.global_scraper import scrape_global_jobs
    result = await run_in_threadpool(scrape_global_jobs)
    return result
