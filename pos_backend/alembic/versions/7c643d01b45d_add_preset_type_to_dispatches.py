"""add_preset_type_to_dispatches

Revision ID: 7c643d01b45d
Revises: b261e8ceb69f
Create Date: 2026-06-18 10:42:56.304606
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c643d01b45d'
down_revision: Union[str, None] = 'b261e8ceb69f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('dispatches',
        sa.Column('preset_type', sa.String(10), nullable=False,
                  server_default=sa.text("'MONEY'"),
                  comment="Preset type: MONEY, VOLUME, or FULL"))
    # Backfill: FULL presets are VOLUME type
    op.execute("UPDATE dispatches SET preset_type = 'VOLUME' WHERE preset_value = 'FULL'")


def downgrade() -> None:
    op.drop_column('dispatches', 'preset_type')
