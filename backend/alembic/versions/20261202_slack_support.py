"""Dedicated Slack support (Enterprise): slack_requests, and priority on support_tickets.

Idempotent: safe on databases already touched by startup create_all.
"""
import sqlalchemy as sa
from alembic import op

revision = "20261202_slack_support"
down_revision = "20261201_brandings"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    from backend.app.models.support import SlackRequest
    SlackRequest.__table__.create(bind, checkfirst=True)
    existing = {c["name"] for c in sa.inspect(bind).get_columns("support_tickets")}
    if "priority" not in existing:
        op.add_column("support_tickets", sa.Column("priority", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column("support_tickets", "priority")
    op.drop_table("slack_requests")
