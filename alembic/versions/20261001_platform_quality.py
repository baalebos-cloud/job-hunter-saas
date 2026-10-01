"""Resume attachments, approved roles and job freshness.

Also accepts databases already updated by the previous startup DDL.
"""
from alembic import op
import sqlalchemy as sa

revision = '20261001_platform_quality'
down_revision = 'f3e7bed01971'
branch_labels = None
depends_on = None


def upgrade():
    columns = {
        'users': [sa.Column('hr_approved', sa.Boolean(), nullable=False, server_default=sa.false()),
                  sa.Column('referral_code', sa.String(), nullable=True)],
        'applications': [sa.Column('resume_id', sa.Integer(), nullable=True),
                         sa.Column('job_snapshot', sa.JSON(), nullable=True),
                         sa.Column('submission_method', sa.String(), nullable=True)],
        'jobs': [sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
                 sa.Column('last_checked_at', sa.DateTime(), nullable=True),
                 sa.Column('published_at', sa.DateTime(), nullable=True)],
    }
    inspector = sa.inspect(op.get_bind())
    for table, additions in columns.items():
        existing = {col['name'] for col in inspector.get_columns(table)}
        for column in additions:
            if column.name not in existing:
                op.add_column(table, column)
    inspector = sa.inspect(op.get_bind())
    unique = inspector.get_unique_constraints('users') + inspector.get_indexes('users')
    if not any(item.get('unique', True) and item['column_names'] == ['referral_code'] for item in unique):
        op.create_index('uq_users_referral_code', 'users', ['referral_code'], unique=True)
    if not any(fk['constrained_columns'] == ['resume_id'] for fk in inspector.get_foreign_keys('applications')):
        with op.batch_alter_table('applications') as batch:
            batch.create_foreign_key('fk_applications_resume_id', 'resumes', ['resume_id'], ['id'])


def downgrade():
    # These fields contain application evidence; retain them on code rollback.
    raise RuntimeError('Restore a database backup to remove application evidence fields.')
