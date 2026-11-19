import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import make_url
from dotenv import load_dotenv

# Load .env for local dev — on Railway env vars are injected directly
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, "../../.env"))

# Railway injects DATABASE_URL automatically via the PostgreSQL plugin
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "")

# Backward-compatible alias
SQLALCHEMY_DATABASE = SQLALCHEMY_DATABASE_URL

if not SQLALCHEMY_DATABASE_URL:
    raise ValueError(
        "DATABASE_URL is not set.\n"
        "  Local: add it to your .env file\n"
        "  Railway: add the PostgreSQL plugin to your project"
    )

# Railway PostgreSQL URLs start with postgres:// — SQLAlchemy needs postgresql://
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

db_scheme = make_url(SQLALCHEMY_DATABASE_URL).get_backend_name()
engine_kwargs = {"pool_pre_ping": True}
if db_scheme == "sqlite":
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # Production pool settings for Railway/RDS
    engine_kwargs["pool_size"] = 5
    engine_kwargs["max_overflow"] = 10
    engine_kwargs["pool_timeout"] = 30

engine = create_engine(SQLALCHEMY_DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Read replica (optional) ──────────────────────────────────────────────────
# DATABASE_READ_URL points at an RDS read replica (typically behind PgBouncer
# in transaction mode). Read-only GET endpoints use ``get_read_db``; anything
# that must read its own writes (resume status/preview) stays on the primary.
_read_url = os.getenv("DATABASE_READ_URL", "")
if _read_url.startswith("postgres://"):
    _read_url = _read_url.replace("postgres://", "postgresql://", 1)
if _read_url:
    from sqlalchemy.pool import NullPool
    _read_kwargs = {"pool_pre_ping": True}
    if os.getenv("DATABASE_READ_POOLER", "").lower() == "pgbouncer":
        # PgBouncer owns pooling; avoid double pooling and stale server state.
        _read_kwargs = {"poolclass": NullPool}
    else:
        _read_kwargs.update(pool_size=10, max_overflow=20, pool_timeout=10)
    read_engine = create_engine(_read_url, **_read_kwargs)
    ReadSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=read_engine)
else:
    read_engine = engine
    ReadSessionLocal = None


from fastapi import Depends  # noqa: E402  (FastAPI dependency wiring)


def get_read_db(primary=Depends(get_db)):
    """Read-only session on the replica, or the primary when none is set."""
    # Depends(get_db) keeps test overrides of get_db effective; the primary
    # session is lazy and opens no connection unless used.
    if ReadSessionLocal is None:
        yield primary
        return
    session = ReadSessionLocal()
    try:
        yield session
    finally:
        session.close()


def pool_status() -> dict:
    """Connection-pool saturation for metrics."""
    def describe(eng):
        pool = eng.pool
        size = getattr(pool, "size", lambda: 0)()
        checked_out = getattr(pool, "checkedout", lambda: 0)()
        return {"size": size, "checked_out": checked_out,
                "overflow": getattr(pool, "overflow", lambda: 0)()}
    return {"write": describe(engine), "read": describe(read_engine)}
