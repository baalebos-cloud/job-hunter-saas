"""Resume Studio documents saved to the account (idempotent)."""
import sqlalchemy as sa
from alembic import op

revision = "20261209_studio_documents"
down_revision = "20261208_profile_resume"
branch_labels = None
depends_on = None


def upgrade():
    from backend.app.models.studio import StudioDocument
    StudioDocument.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    if "studio_documents" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("studio_documents")
