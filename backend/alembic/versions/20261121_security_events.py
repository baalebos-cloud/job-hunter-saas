"""Security events for owner oversight (full IP and location, purpose-limited).

See backend/app/models/security_event.py. Rows are deleted by the retention
job after SECURITY_EVENT_RETENTION_DAYS and on account erasure.
"""
from alembic import op

revision = "20261121_security_events"
down_revision = "20261120_audit_privacy"
branch_labels = None
depends_on = None


def upgrade():
    from backend.app.models.security_event import SecurityEvent
    SecurityEvent.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    op.drop_table("security_events")
