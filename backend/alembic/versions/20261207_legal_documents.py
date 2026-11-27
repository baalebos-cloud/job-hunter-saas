"""Legal documents with published version history (idempotent)."""
import sqlalchemy as sa
from alembic import op

revision = "20261207_legal_documents"
down_revision = "20261206_legal_role_invitations"
branch_labels = None
depends_on = None


def upgrade():
    from backend.app.models.legal import LegalDocumentVersion
    LegalDocumentVersion.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    if "legal_document_versions" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("legal_document_versions")
