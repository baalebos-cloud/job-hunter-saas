"""Enterprise team access: team_members.

Idempotent: safe on databases already touched by startup create_all.
"""
from alembic import op

revision = "20261129_team_members"
down_revision = "20261128_resume_batches"
branch_labels = None
depends_on = None


def upgrade():
    from backend.app.models.team import TeamMember
    TeamMember.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    op.drop_table("team_members")
