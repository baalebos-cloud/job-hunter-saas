"""Bulk resume processing (Enterprise): resume_batches.

Idempotent: safe on databases already touched by startup create_all.
"""
from alembic import op

revision = "20261128_resume_batches"
down_revision = "20261127_job_alert_prefs"
branch_labels = None
depends_on = None


def upgrade():
    from backend.app.models.resume import ResumeBatch
    ResumeBatch.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    op.drop_table("resume_batches")
