"""add_is_active_to_grades

Revision ID: 5a02d184d729
Revises: 7c643d01b45d
Create Date: 2026-06-22 11:08:59.254401
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5a02d184d729'
down_revision: Union[str, None] = '7c643d01b45d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: add nullable column
    op.add_column('grades', sa.Column('is_active', sa.Boolean(), nullable=True))
    # Step 2: backfill existing grades
    op.execute("UPDATE grades SET is_active = TRUE WHERE is_active IS NULL")
    # Step 3: enforce NOT NULL with default
    op.alter_column('grades', 'is_active', nullable=False, existing_type=sa.Boolean(), server_default=sa.text('true'))


def downgrade() -> None:
    op.drop_column('grades', 'is_active')
