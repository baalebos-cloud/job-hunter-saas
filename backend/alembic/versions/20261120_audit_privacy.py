"""Append-only audit trail and erasure tombstones.

PostgreSQL: a trigger rejects UPDATE and DELETE on audit_logs unless the
transaction set ``app.audit_retention = 'on'`` (retention job only).
"""
import sqlalchemy as sa
from alembic import op

revision = "20261120_audit_privacy"
down_revision = "20261119_storage_and_indexes"
branch_labels = None
depends_on = None

TRIGGER_FN = """
CREATE OR REPLACE FUNCTION audit_logs_append_only() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' AND current_setting('app.audit_retention', true) = 'on' THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'audit_logs is append-only';
END;
$$ LANGUAGE plpgsql;
"""


def upgrade():
    bind = op.get_bind()
    from backend.app.models.audit import AuditLog, ErasureTombstone
    AuditLog.__table__.create(bind, checkfirst=True)
    ErasureTombstone.__table__.create(bind, checkfirst=True)
    if bind.dialect.name == "postgresql":
        op.execute(TRIGGER_FN)
        op.execute("DROP TRIGGER IF EXISTS audit_logs_append_only ON audit_logs")
        op.execute("CREATE TRIGGER audit_logs_append_only BEFORE UPDATE OR DELETE ON audit_logs "
                   "FOR EACH ROW EXECUTE FUNCTION audit_logs_append_only()")
        op.execute("DROP TRIGGER IF EXISTS audit_logs_no_truncate ON audit_logs")
        op.execute("CREATE TRIGGER audit_logs_no_truncate BEFORE TRUNCATE ON audit_logs "
                   "FOR EACH STATEMENT EXECUTE FUNCTION audit_logs_append_only()")


def downgrade():
    raise RuntimeError("Audit evidence is retained; restore from backup to remove it.")
