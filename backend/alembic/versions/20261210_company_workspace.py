"""Employer workspaces: companies, team members, hiring teams; jobs.company_id.

Every existing employer account becomes the admin of its own company, and the
jobs it posted move into that company, so nobody loses access (idempotent).
"""
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision = "20261210_company_workspace"
down_revision = "20261209_studio_documents"
branch_labels = None
depends_on = None


def upgrade():
    from backend.app.models.company import Company, CompanyMember, JobTeamMember
    bind = op.get_bind()
    for model in (Company, CompanyMember, JobTeamMember):
        model.__table__.create(bind, checkfirst=True)
    columns = {c["name"] for c in sa.inspect(bind).get_columns("jobs")}
    if "company_id" not in columns:
        with op.batch_alter_table("jobs") as batch:
            batch.add_column(sa.Column("company_id", sa.Integer(), nullable=True))
            batch.create_foreign_key("fk_jobs_company_id", "companies", ["company_id"], ["id"], ondelete="SET NULL")
            batch.create_index("ix_jobs_company_id", ["company_id"])

    from backend.app.services.account_integrity import canonical_email
    users = sa.table("users", sa.column("id"), sa.column("email"), sa.column("company_name"), sa.column("company_url"),
                     sa.column("country"), sa.column("is_hr"), sa.column("hr_approved"))
    companies, members = Company.__table__, CompanyMember.__table__
    jobs = sa.table("jobs", sa.column("company_id"), sa.column("hr_user_id"))
    joined = {r.user_id for r in bind.execute(sa.select(members.c.user_id)) if r.user_id}
    now = datetime.utcnow()
    for user in bind.execute(sa.select(users).where(users.c.is_hr == sa.true())).fetchall():
        if user.id in joined:
            continue
        name = (user.company_name or user.email.split("@")[-1]).strip()[:200]
        company_id = bind.execute(companies.insert().values(
            name=name, website=user.company_url, country=user.country, created_by=user.id,
            approved_at=now if user.hr_approved else None, created_at=now)).inserted_primary_key[0]
        bind.execute(members.insert().values(
            company_id=company_id, user_id=user.id, email=user.email.lower(), email_canonical=canonical_email(user.email),
            role="admin", status="active", invited_at=now, accepted_at=now))
        bind.execute(jobs.update().where(jobs.c.hr_user_id == user.id, jobs.c.company_id.is_(None))
                     .values(company_id=company_id))


def downgrade():
    bind = op.get_bind()
    if "company_id" in {c["name"] for c in sa.inspect(bind).get_columns("jobs")}:
        with op.batch_alter_table("jobs") as batch:
            batch.drop_index("ix_jobs_company_id")
            batch.drop_constraint("fk_jobs_company_id", type_="foreignkey")
            batch.drop_column("company_id")
    tables = sa.inspect(bind).get_table_names()
    for name in ("job_team_members", "company_members", "companies"):
        if name in tables:
            op.drop_table(name)
