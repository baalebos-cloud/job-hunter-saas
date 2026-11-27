"""Resume kept on the profile, and several tracks / work types / countries at sign-up (idempotent)."""
import sqlalchemy as sa
from alembic import op

revision = "20261208_profile_resume_multiselect"
down_revision = "20261207_legal_documents"
branch_labels = None
depends_on = None

COLUMNS = ("career_tracks", "work_types", "work_countries")


def upgrade():
    bind = op.get_bind()
    existing = {c["name"] for c in sa.inspect(bind).get_columns("users")}
    for name in COLUMNS:
        if name not in existing:
            op.add_column("users", sa.Column(name, sa.JSON(), nullable=True))
    from backend.app.models.user import ProfileResume
    ProfileResume.__table__.create(bind, checkfirst=True)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "profile_resumes" in inspector.get_table_names():
        op.drop_table("profile_resumes")
    existing = {c["name"] for c in inspector.get_columns("users")}
    for name in COLUMNS:
        if name in existing:
            op.drop_column("users", name)
