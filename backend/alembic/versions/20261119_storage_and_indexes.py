"""Object-storage columns for resumes and hot-path composite indexes.

* resumes: storage_key, sha256, size_bytes, status, error, timestamps;
  ``content`` becomes nullable (expand phase - PDFs move to S3 with
  ``python -m backend.scripts.migrate_resume_blobs``; the column is dropped
  in a later contract migration once the backfill is verified)
* indexes built with CREATE INDEX CONCURRENTLY on PostgreSQL (no write locks)
"""
import logging

import sqlalchemy as sa
from alembic import op

revision = "20261119_storage_and_indexes"
down_revision = "20261118_security_rbac"
branch_labels = None
depends_on = None
log = logging.getLogger("alembic.runtime.migration")

INDEXES = [
    # name, table, columns sql, unique
    ("uq_resumes_owner_filename", "resumes", "(owner_id, filename)", True),
    ("ix_applications_user_created", "applications", "(user_id, created_at DESC)", False),
    ("ix_applications_job_status", "applications", "(job_id, status)", False),
    ("ix_jobs_active_work_type", "jobs", "(is_active, work_type)", False),
    ("ix_users_verification_token", "users", "(verification_token)", False),
    ("ix_users_reset_token", "users", "(reset_token)", False),
]


def upgrade():
    bind = op.get_bind()
    existing = {c["name"] for c in sa.inspect(bind).get_columns("resumes")}
    additions = [
        sa.Column("storage_key", sa.String(512), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="completed"),
        sa.Column("error", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    ]
    for column in additions:
        if column.name not in existing:
            op.add_column("resumes", column)
    if bind.dialect.name == "postgresql":
        op.alter_column("resumes", "content", existing_type=sa.LargeBinary(), nullable=True)
    else:  # SQLite needs a table rebuild to relax NOT NULL
        with op.batch_alter_table("resumes") as batch:
            batch.alter_column("content", existing_type=sa.LargeBinary(), nullable=True)

    present = {i["name"] for t in {i[1] for i in INDEXES} for i in sa.inspect(bind).get_indexes(t)}
    duplicate_resumes = bind.execute(sa.text(
        "SELECT COUNT(*) FROM (SELECT owner_id, filename FROM resumes GROUP BY owner_id, filename HAVING COUNT(*) > 1) d")).scalar()
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            for name, table, columns, unique in INDEXES:
                if name in present:
                    continue
                if unique and duplicate_resumes:
                    log.warning("Skipping %s: %s duplicate (owner_id, filename) pairs must be resolved first", name, duplicate_resumes)
                    continue
                # A failed concurrent build leaves an INVALID index; drop it before retrying.
                op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
                op.execute(f"CREATE {'UNIQUE ' if unique else ''}INDEX CONCURRENTLY {name} ON {table} {columns}")
    else:
        for name, table, columns, unique in INDEXES:
            if name not in present and not (unique and duplicate_resumes):
                op.execute(f"CREATE {'UNIQUE ' if unique else ''}INDEX IF NOT EXISTS {name} ON {table} {columns.replace(' DESC', '')}")


def downgrade():
    for name, table, _, _ in INDEXES:
        op.drop_index(name, table_name=table)
    for column in ("updated_at", "created_at", "error", "status", "size_bytes", "sha256", "storage_key"):
        op.drop_column("resumes", column)
