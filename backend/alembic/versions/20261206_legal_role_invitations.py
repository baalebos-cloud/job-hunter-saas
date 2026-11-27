"""Legal counsel role and staff role invitations.

Idempotent. Adds the staff_invitations table, and on databases whose policy
matrix is already seeded: the legal_counsel role with its permissions, and the
new legal:manage permission for super_admin. Existing role holders keep their
roles; only new assignments go through an invitation.
"""
import sqlalchemy as sa
from alembic import op

revision = "20261206_legal_role_invitations"
down_revision = "20261205_signup_integrity"
branch_labels = None
depends_on = None

LEGAL = ("Legal: policies, data-protection requests and the audit trail",
         ["legal:manage", "privacy:manage", "audit:read", "users:read"])


def upgrade():
    bind = op.get_bind()
    from backend.app.models.security import StaffInvitation
    StaffInvitation.__table__.create(bind, checkfirst=True)
    tables = set(sa.inspect(bind).get_table_names())
    if not {"rbac_roles", "rbac_role_permissions"} <= tables:
        return
    present_roles = {r[0] for r in bind.execute(sa.text("SELECT name FROM rbac_roles"))}
    if not present_roles:
        return          # matrix seeded from code (which includes legal_counsel) on first use
    present = {(r[0], r[1]) for r in bind.execute(sa.text("SELECT role, permission FROM rbac_role_permissions"))}
    roles = sa.table("rbac_roles", sa.column("name"), sa.column("description"), sa.column("is_system"))
    perms = sa.table("rbac_role_permissions", sa.column("role"), sa.column("permission"))
    if "legal_counsel" not in present_roles:
        bind.execute(roles.insert().values(name="legal_counsel", description=LEGAL[0], is_system=True))
        for permission in LEGAL[1]:
            bind.execute(perms.insert().values(role="legal_counsel", permission=permission))
    if "super_admin" in present_roles and ("super_admin", "legal:manage") not in present:
        bind.execute(perms.insert().values(role="super_admin", permission="legal:manage"))


def downgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "staff_invitations" in tables:
        op.drop_table("staff_invitations")
    if "rbac_role_permissions" in tables:
        bind.execute(sa.text("DELETE FROM rbac_role_permissions WHERE role = 'legal_counsel' OR permission = 'legal:manage'"))
    if "rbac_roles" in tables:
        bind.execute(sa.text("DELETE FROM rbac_roles WHERE name = 'legal_counsel'"))
