"""Sessions, token hashing and database-backed RBAC.

* users.role, users.token_version
* refresh_tokens, rbac_roles, rbac_role_permissions (+ default matrix)
* existing verification/reset tokens are replaced by their SHA-256 hashes
  (links already emailed keep working because lookups hash the raw token)
* bootstrap super_admin: the verified account matching ADMIN_EMAIL, or, if
  ADMIN_EMAIL is unset, verified accounts that already had is_admin = true

Idempotent: safe on databases already touched by startup create_all.
"""
import hashlib
import os

import sqlalchemy as sa
from alembic import op

revision = "20261118_security_rbac"
down_revision = "20261010_job_automation"
branch_labels = None
depends_on = None


def _columns(bind, table):
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade():
    bind = op.get_bind()
    existing = _columns(bind, "users")
    if "role" not in existing:
        op.add_column("users", sa.Column("role", sa.String(), nullable=True))
    if "token_version" not in existing:
        op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))
    if not any(i["name"] == "ix_users_role" for i in sa.inspect(bind).get_indexes("users")):
        op.create_index("ix_users_role", "users", ["role"])

    from backend.app.models.security import RbacPermission, RbacRole, RefreshToken
    for model in (RbacRole, RbacPermission, RefreshToken):
        model.__table__.create(bind, checkfirst=True)

    # Seed the default policy matrix.
    from backend.app.dependencies.roles import DEFAULT_MATRIX
    if not bind.execute(sa.text("SELECT COUNT(*) FROM rbac_roles")).scalar():
        for role, (description, permissions) in DEFAULT_MATRIX.items():
            bind.execute(sa.text("INSERT INTO rbac_roles (name, description, is_system) VALUES (:n, :d, :s)"),
                         {"n": role, "d": description, "s": True})
            for permission in permissions:
                bind.execute(sa.text("INSERT INTO rbac_role_permissions (role, permission) VALUES (:r, :p)"),
                             {"r": role, "p": permission})

    # Hash outstanding plaintext verification/reset tokens (64-hex values are
    # already hashes and are left alone).
    for column in ("verification_token", "reset_token"):
        rows = bind.execute(sa.text(f"SELECT id, {column} FROM users WHERE {column} IS NOT NULL")).fetchall()
        for user_id, token in rows:
            if len(token) == 64 and all(c in "0123456789abcdef" for c in token):
                continue
            bind.execute(sa.text(f"UPDATE users SET {column} = :h WHERE id = :i"),
                         {"h": hashlib.sha256(token.encode("utf-8")).hexdigest(), "i": user_id})

    # Bootstrap the first super_admin (replaces the hard-coded owner email).
    admin_email = (os.getenv("ADMIN_EMAIL") or "").strip().lower()
    if not bind.execute(sa.text("SELECT COUNT(*) FROM users WHERE role = 'super_admin'")).scalar():
        if admin_email:
            bind.execute(sa.text("UPDATE users SET role = 'super_admin', is_admin = :t "
                                 "WHERE lower(email) = :e AND is_verified = :t"), {"e": admin_email, "t": True})
        else:
            bind.execute(sa.text("UPDATE users SET role = 'super_admin' WHERE is_admin = :t AND is_verified = :t"),
                         {"t": True})


def downgrade():
    op.drop_table("refresh_tokens")
    op.drop_table("rbac_role_permissions")
    op.drop_table("rbac_roles")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_column("users", "token_version")
    op.drop_column("users", "role")
