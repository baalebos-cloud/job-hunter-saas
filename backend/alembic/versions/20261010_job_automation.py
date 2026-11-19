"""Notification outbox, scrape runs and opt-in preferences.

Safe on installations already updated by startup create_all / DDL.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261010_job_automation"
down_revision = "20261001_platform_quality"
branch_labels = None
depends_on = None


def upgrade():
    columns = {
        "users": [sa.Column("job_alerts_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
                  sa.Column("job_alerts_enabled_at", sa.DateTime(), nullable=True),
                  sa.Column("job_alert_work_type", sa.String(), nullable=False, server_default="all")],
        "jobs": [sa.Column("first_seen_at", sa.DateTime(), nullable=True)],
    }
    inspector = sa.inspect(op.get_bind())
    for table, additions in columns.items():
        existing = {column["name"] for column in inspector.get_columns(table)}
        for column in additions:
            if column.name not in existing:
                op.add_column(table, column)
    from backend.app.models.automation import AutomationEvent, ScrapeRun, AutomationState
    for model in (AutomationEvent, ScrapeRun, AutomationState):
        model.__table__.create(op.get_bind(), checkfirst=True)
    indexes = sa.inspect(op.get_bind()).get_indexes("jobs")
    if not any(index["column_names"] == ["first_seen_at"] for index in indexes):
        op.create_index("ix_jobs_first_seen_at", "jobs", ["first_seen_at"])


def downgrade():
    # Retain consent and delivery evidence on application rollback.
    raise RuntimeError("Restore a database backup to remove notification history.")
