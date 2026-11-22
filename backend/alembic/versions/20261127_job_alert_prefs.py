"""Job alert preferences: frequency (daily/weekly) and minimum match %.

Idempotent: safe on databases already touched by startup create_all.
"""
import sqlalchemy as sa
from alembic import op

revision = "20261127_job_alert_prefs"
down_revision = "20261126_job_dedupe"
branch_labels = None
depends_on = None


def upgrade():
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("users")}
    if "job_alert_frequency" not in existing:
        op.add_column("users", sa.Column("job_alert_frequency", sa.String(10), nullable=False, server_default="daily"))
    if "job_alert_min_match" not in existing:
        op.add_column("users", sa.Column("job_alert_min_match", sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    op.drop_column("users", "job_alert_min_match")
    op.drop_column("users", "job_alert_frequency")
