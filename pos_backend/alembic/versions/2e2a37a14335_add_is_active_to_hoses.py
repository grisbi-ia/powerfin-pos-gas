"""add_is_active_to_hoses

Revision ID: 2e2a37a14335
Revises: c7ccad66cca6
Create Date: 2026-06-22 11:35:52.081262
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2e2a37a14335'
down_revision: Union[str, None] = 'c7ccad66cca6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add nullable, backfill, enforce NOT NULL
    op.add_column('hoses', sa.Column('is_active', sa.Boolean(), nullable=True))
    op.execute("UPDATE hoses SET is_active = TRUE WHERE is_active IS NULL")
    op.alter_column('hoses', 'is_active', nullable=False, existing_type=sa.Boolean(), server_default=sa.text('true'))


def downgrade() -> None:
    op.drop_column('hoses', 'is_active')
