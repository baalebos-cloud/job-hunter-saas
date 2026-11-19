"""fix double heads

Revision ID: f3e7bed01971
Revises: 001_add_career_track, e2d575bef224
Create Date: 2026-04-27 01:59:05.865411

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3e7bed01971'
down_revision: Union[str, None] = ('001_add_career_track', 'e2d575bef224')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
