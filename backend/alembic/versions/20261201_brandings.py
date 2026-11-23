"""Custom branding on exports (Enterprise): brandings.

Idempotent: safe on databases already touched by startup create_all.
"""
from alembic import op

revision = "20261201_brandings"
down_revision = "20261130_api_keys"
branch_labels = None
depends_on = None


def upgrade():
    from backend.app.models.branding import Branding
    Branding.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    op.drop_table("brandings")
