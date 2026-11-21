"""Job board fields: de-duplication key, extracted skills, employment type, logo.

Idempotent: safe on databases already touched by startup create_all.
"""
import sqlalchemy as sa
from alembic import op

revision = "20261123_job_board"
down_revision = "20261122_account_integrity"
branch_labels = None
depends_on = None

COLUMNS = [
    ("dedupe_key", sa.String(300)),
    ("skills", sa.JSON()),
    ("employment_type", sa.String(32)),
    ("company_logo", sa.String(500)),
]


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("jobs")}
    for name, type_ in COLUMNS:
        if name not in existing:
            op.add_column("jobs", sa.Column(name, type_, nullable=True))
    if not any(i["name"] == "ix_jobs_dedupe_key" for i in inspector.get_indexes("jobs")):
        op.create_index("ix_jobs_dedupe_key", "jobs", ["dedupe_key"])


def downgrade():
    op.drop_index("ix_jobs_dedupe_key", table_name="jobs")
    for name, _ in reversed(COLUMNS):
        op.drop_column("jobs", name)
