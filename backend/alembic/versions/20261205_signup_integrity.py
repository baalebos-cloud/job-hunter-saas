"""Sign-up integrity: network/device fingerprint on users and owner-managed sign-up rules.

Idempotent. Existing accounts keep NULL fingerprints: they are never blocked
retroactively, and only accounts created after this migration are grouped.
"""
import sqlalchemy as sa
from alembic import op

revision = "20261205_signup_integrity"
down_revision = "20261204_application_forms"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("users")}
    indexes = {i["name"] for i in inspector.get_indexes("users")}
    for name in ("signup_network", "signup_device"):
        if name not in columns:
            op.add_column("users", sa.Column(name, sa.String(64), nullable=True))
        if f"ix_users_{name}" not in indexes:
            op.create_index(f"ix_users_{name}", "users", [name])
    from backend.app.models.security import SignupRule
    SignupRule.__table__.create(bind, checkfirst=True)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "signup_rules" in inspector.get_table_names():
        op.drop_table("signup_rules")
    columns = {c["name"] for c in inspector.get_columns("users")}
    indexes = {i["name"] for i in inspector.get_indexes("users")}
    for name in ("signup_network", "signup_device"):
        if f"ix_users_{name}" in indexes:
            op.drop_index(f"ix_users_{name}", table_name="users")
        if name in columns:
            op.drop_column("users", name)
