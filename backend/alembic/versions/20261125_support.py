"""Help & support: tickets and their message threads.

Idempotent: safe on databases already touched by startup create_all.
"""
from alembic import op

revision = "20261125_support"
down_revision = "20261124_profile_photos"
branch_labels = None
depends_on = None


def upgrade():
    from backend.app.models.support import SupportMessage, SupportTicket
    bind = op.get_bind()
    SupportTicket.__table__.create(bind, checkfirst=True)
    SupportMessage.__table__.create(bind, checkfirst=True)


def downgrade():
    op.drop_table("support_messages")
    op.drop_table("support_tickets")
