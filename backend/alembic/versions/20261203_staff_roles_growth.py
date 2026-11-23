"""Team console: product_manager and social_media_manager roles, campaign
attribution on users, and daily go-to-market counters (counts only).

Idempotent: safe on databases already touched by startup create_all. Existing
roles and any permission changes made in Access control are left untouched;
only missing roles and the new console permissions for super_admin are added.
"""
import sqlalchemy as sa
from alembic import op

revision = "20261203_staff_roles_growth"
down_revision = "20261202_slack_support"
branch_labels = None
depends_on = None

NEW_ROLES = {
    "product_manager": ("Product, go-to-market and customer support",
                        ["analytics:read", "growth:read", "campaigns:read", "content:read", "support:manage",
                         "reports:read", "metrics:read"]),
    "social_media_manager": ("Social media: content insights and campaign results (no personal data)",
                             ["analytics:read", "campaigns:read", "content:read"]),
}
NEW_PERMISSIONS = ["analytics:read", "growth:read", "campaigns:read", "content:read", "support:manage"]
USER_COLUMNS = [("signup_utm_source", 80), ("signup_utm_medium", 80), ("signup_utm_campaign", 120),
                ("signup_referrer", 120)]


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("users")}
    for name, length in USER_COLUMNS:
        if name not in existing:
            op.add_column("users", sa.Column(name, sa.String(length), nullable=True))

    from backend.app.models.growth import GrowthCounter
    GrowthCounter.__table__.create(bind, checkfirst=True)

    tables = set(inspector.get_table_names())
    if not {"rbac_roles", "rbac_role_permissions"} <= tables:
        return          # policy tables are created and seeded on first use
    roles = sa.table("rbac_roles", sa.column("name"), sa.column("description"), sa.column("is_system"))
    perms = sa.table("rbac_role_permissions", sa.column("role"), sa.column("permission"))
    present_roles = {r[0] for r in bind.execute(sa.text("SELECT name FROM rbac_roles"))}
    if not present_roles:
        return          # empty matrix: seeded from code (which already includes the new roles) on first use
    present = {(r[0], r[1]) for r in bind.execute(sa.text("SELECT role, permission FROM rbac_role_permissions"))}
    for role, (description, permissions) in NEW_ROLES.items():
        if role not in present_roles:
            bind.execute(roles.insert().values(name=role, description=description, is_system=True))
            for permission in permissions:
                bind.execute(perms.insert().values(role=role, permission=permission))
    if "super_admin" in present_roles:
        for permission in NEW_PERMISSIONS:
            if ("super_admin", permission) not in present:
                bind.execute(perms.insert().values(role="super_admin", permission=permission))


def downgrade():
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM rbac_role_permissions WHERE role IN ('product_manager', 'social_media_manager')"))
    bind.execute(sa.text("DELETE FROM rbac_roles WHERE name IN ('product_manager', 'social_media_manager')"))
    op.drop_table("growth_counters")
    for name, _ in USER_COLUMNS:
        op.drop_column("users", name)
