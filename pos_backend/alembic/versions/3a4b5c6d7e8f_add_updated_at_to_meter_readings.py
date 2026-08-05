"""add_updated_at_to_meter_readings

Revision ID: 3a4b5c6d7e8f
Revises: 2f3a4b5c6d7e
Create Date: 2026-07-10 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a4b5c6d7e8f'
down_revision: Union[str, None] = '2f3a4b5c6d7e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('meter_readings',
                  sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))
    # Backfill: set updated_at = recorded_at for existing rows
    op.execute("UPDATE meter_readings SET updated_at = recorded_at WHERE updated_at IS NULL")


def downgrade() -> None:
    op.drop_column('meter_readings', 'updated_at')
