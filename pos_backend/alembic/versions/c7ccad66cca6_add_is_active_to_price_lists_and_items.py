"""add_is_active_to_price_lists_and_items

Revision ID: c7ccad66cca6
Revises: 5a02d184d729
Create Date: 2026-06-22 11:27:57.823197
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7ccad66cca6'
down_revision: Union[str, None] = '5a02d184d729'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Price lists: add nullable, backfill, enforce NOT NULL
    op.add_column('price_lists', sa.Column('is_active', sa.Boolean(), nullable=True))
    op.execute("UPDATE price_lists SET is_active = TRUE WHERE is_active IS NULL")
    op.alter_column('price_lists', 'is_active', nullable=False, existing_type=sa.Boolean(), server_default=sa.text('true'))

    # Price list items: add nullable, backfill, enforce NOT NULL
    op.add_column('price_list_items', sa.Column('is_active', sa.Boolean(), nullable=True))
    op.execute("UPDATE price_list_items SET is_active = TRUE WHERE is_active IS NULL")
    op.alter_column('price_list_items', 'is_active', nullable=False, existing_type=sa.Boolean(), server_default=sa.text('true'))


def downgrade() -> None:
    op.drop_column('price_list_items', 'is_active')
    op.drop_column('price_lists', 'is_active')
