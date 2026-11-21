"""Account integrity and owner security controls.

* users: email_canonical (+ backfill), signup_ip, suspension, forced password
  reset, last sign-in, TOTP two-step verification, employer review fields
* blocked_ips, dismissed_duplicates

Idempotent: safe on databases already touched by startup create_all.
"""
import sqlalchemy as sa
from alembic import op

revision = "20261122_account_integrity"
down_revision = "20261121_security_events"
branch_labels = None
depends_on = None

USER_COLUMNS = [
    ("email_canonical", sa.String(255), {}),
    ("signup_ip", sa.String(64), {}),
    ("suspended_at", sa.DateTime(), {}),
    ("suspended_reason", sa.String(255), {}),
    ("force_password_reset", sa.Boolean(), {"nullable": False, "server_default": sa.false()}),
    ("last_login_at", sa.DateTime(), {}),
    ("last_login_ip", sa.String(64), {}),
    ("last_login_location", sa.String(128), {}),
    ("totp_secret", sa.String(255), {}),
    ("totp_enabled_at", sa.DateTime(), {}),
    ("totp_recovery_codes", sa.JSON(), {}),
    ("company_url", sa.String(255), {}),
    ("hr_job_title", sa.String(128), {}),
    ("hr_rejected_at", sa.DateTime(), {}),
    ("hr_rejected_reason", sa.String(255), {}),
]


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("users")}
    for name, type_, kwargs in USER_COLUMNS:
        if name not in existing:
            op.add_column("users", sa.Column(name, type_, nullable=kwargs.get("nullable", True),
                                             server_default=kwargs.get("server_default")))
    if not any(i["name"] == "ix_users_email_canonical" for i in inspector.get_indexes("users")):
        op.create_index("ix_users_email_canonical", "users", ["email_canonical"])

    from backend.app.services.account_integrity import canonical_email
    rows = bind.execute(sa.text("SELECT id, email FROM users WHERE email_canonical IS NULL")).fetchall()
    for user_id, email in rows:
        bind.execute(sa.text("UPDATE users SET email_canonical = :c WHERE id = :i"),
                     {"c": canonical_email(email), "i": user_id})

    from backend.app.models.security import BlockedIP, DismissedDuplicate
    for model in (BlockedIP, DismissedDuplicate):
        model.__table__.create(bind, checkfirst=True)


def downgrade():
    op.drop_table("dismissed_duplicates")
    op.drop_table("blocked_ips")
    op.drop_index("ix_users_email_canonical", table_name="users")
    for name, _, _ in reversed(USER_COLUMNS):
        op.drop_column("users", name)
