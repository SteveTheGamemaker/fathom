"""add preferred_source to quality_profiles

Revision ID: a3f8e2b91c05
Revises: dc5deea1b1e3
Create Date: 2026-04-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f8e2b91c05'
down_revision: Union[str, Sequence[str], None] = 'dc5deea1b1e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'quality_profiles',
        sa.Column('preferred_source', sa.String(), nullable=False, server_default='any'),
    )


def downgrade() -> None:
    op.drop_column('quality_profiles', 'preferred_source')
