"""add career_track to users

Revision ID: 001_add_career_track
Revises:
Create Date: 2026-04-25
"""
from alembic import op
import sqlalchemy as sa

revision = '001_add_career_track'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('career_track', sa.String(), nullable=True))


def downgrade():
    op.drop_column('users', 'career_track')