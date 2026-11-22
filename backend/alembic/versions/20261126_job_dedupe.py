"""Close duplicate job listings already stored (one per role per company).

Rows saved before dedupe keys existed had none, so the same vacancy could be
listed many times. Recomputes every active job's key and keeps one listing per
role per company (employer posting > applied-to > first seen). Data only and
idempotent: re-running closes nothing new.
"""
from alembic import op
from sqlalchemy.orm import Session

revision = "20261126_job_dedupe"
down_revision = "20261125_support"
branch_labels = None
depends_on = None


def upgrade():
    from backend.app.models.registry import import_all_models
    from backend.app.utils.global_scraper import collapse_duplicate_jobs
    import_all_models()
    session = Session(bind=op.get_bind())
    try:
        collapse_duplicate_jobs(session)
    finally:
        session.close()


def downgrade():
    pass   # closed duplicates are not reopened
