"""Enterprise integrations API: api_keys.

Idempotent: safe on databases already touched by startup create_all.
"""
from alembic import op

revision = "20261130_api_keys"
down_revision = "20261129_team_members"
branch_labels = None
depends_on = None


def upgrade():
    from backend.app.models.api_key import ApiKey
    ApiKey.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    op.drop_table("api_keys")
