import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import make_url
from dotenv import load_dotenv

# 1. ROBUST PATH LOADING: Find .env in the project root
# This ensures that whether you run from root or from /backend, the URL is found.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, "../../.env"))

# 2. Get the AWS RDS URL
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

#Backward-compatible alias for older references
SQLALCHEMY_DATABASE = SQLALCHEMY_DATABASE_URL

# Safety check for the developer
if not SQLALCHEMY_DATABASE_URL:
    raise ValueError("❌ DATABASE_URL not found. Check your .env file at the project root.")

# Note: PostgreSQL handles threading
db_scheme = make_url(SQLALCHEMY_DATABASE).get_backend_name()
engine_kwargs = {"pool_pre_ping": True}
if db_scheme == "sqlite":
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(SQLALCHEMY_DATABASE_URL, **engine_kwargs)
# 4. Create the Session Factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 5. Define the Base for Models
Base = declarative_base()

# 6. Dependency for FastAPI Routes
def get_db():
    """
    Yields a database session to a request and ensures
    it is closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
