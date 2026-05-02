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
