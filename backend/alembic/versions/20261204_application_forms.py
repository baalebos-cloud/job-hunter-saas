"""Application forms on jobs posted on Baalebos, and the answers sent with each application.

Idempotent: columns are added only when missing (startup create_all may already
have created them on a fresh database). Existing jobs keep a NULL form and use the
default form; existing applications keep NULL answers.
"""
import sqlalchemy as sa
from alembic import op

revision = "20261204_application_forms"
down_revision = "20261203_staff_roles_growth"
branch_labels = None
depends_on = None

COLUMNS = [("jobs", "application_form"), ("applications", "applicant_details"), ("applications", "answers")]


def upgrade():
    inspector = sa.inspect(op.get_bind())
    for table, column in COLUMNS:
        if column not in {c["name"] for c in inspector.get_columns(table)}:
            op.add_column(table, sa.Column(column, sa.JSON(), nullable=True))


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for table, column in COLUMNS:
        if column in {c["name"] for c in inspector.get_columns(table)}:
            op.drop_column(table, column)
