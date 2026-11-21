"""Profile photos stored in the database (they were written to ephemeral disk).

Idempotent: safe on databases already touched by startup create_all.
"""
from alembic import op

revision = "20261124_profile_photos"
down_revision = "20261123_job_board"
branch_labels = None
depends_on = None


def upgrade():
    from backend.app.models.user import ProfilePhoto
    ProfilePhoto.__table__.create(op.get_bind(), checkfirst=True)
    # Photos saved before this release lived on the container disk and are gone.
    op.execute("UPDATE users SET photo_url = NULL WHERE photo_url LIKE '%/api/v1/profile/photo/avatar_%'")


def downgrade():
    op.drop_table("profile_photos")
