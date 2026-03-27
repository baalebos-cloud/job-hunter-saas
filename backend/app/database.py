import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# 1. ROBUST PATH LOADING: Find .env in the project root
# This ensures that whether you run from root or from /backend, the URL is found.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, "../../.env"))

# 2. Get the AWS RDS URL
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

# Safety check for the developer
if not SQLALCHEMY_DATABASE_URL:
    raise ValueError("❌ DATABASE_URL not found. Check your .env file at the project root.")

# 3. Create the Engine
# Note: PostgreSQL handles threading natively, so no extra args needed.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True  # Recommended for RDS to handle dropped idle connections
)

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
