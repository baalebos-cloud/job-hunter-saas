import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv

# 1. FORCE PATH NORMALIZATION
# This ensures that 'backend.app' and 'app' resolve to the same location
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
backend_path = os.path.join(BASE_DIR, 'backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# 2. Load environment variables
load_dotenv()

# 3. THE "SINGLETON" IMPORT
# We must import the Base that ALL models share.
from backend.app.database import Base

# 4. EXPLICIT MODEL LOADING
# We import these to trigger the @Base.metadata.register decoration.
# If 'User' is missing from the list below, the Foreign Key in 'Job' will crash.
try:
    from backend.app.models.user import User
    from backend.app.models.job import Job
    from backend.app.models.resume import Resume
    # Add any other models here (e.g., Application, Profile)
    
    # CRITICAL CHECK: This must print ['users', 'jobs', 'resumes'...]
    detected_tables = list(Base.metadata.tables.keys())
    print(f"✅ [ALEMBIC REGISTRY] Tables detected: {detected_tables}")
    
    if 'users' not in detected_tables:
        print("⚠️ WARNING: 'users' table not found in metadata. Check user.py imports!")
        
except ImportError as e:
    print(f"❌ [ALEMBIC ERROR] Model import failed: {e}")
    raise

# Alembic Config object
config = context.config

# 5. RDS CONNECTION STRING
if os.getenv("DATABASE_URL"):
    config.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL"))

# Standard Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata,
            compare_type=True # Detects changes to column types
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
