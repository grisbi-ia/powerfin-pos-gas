"""add_plate_raw_to_dispatches

Revision ID: 4b5c6d7e8f90
Revises: 3a4b5c6d7e8f
Create Date: 2026-09-12 21:00:00.000000

Keeps the plate the dispatcher typed even when it does not match a registered
vehicle, so an anonymous sale can still be reconciled afterwards. Nullable and
additive — no impact on existing rows or the sale flow.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b5c6d7e8f90'
down_revision: Union[str, None] = '3a4b5c6d7e8f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'dispatches',
        sa.Column(
            'plate_raw',
            sa.String(length=15),
            nullable=True,
            comment="Plate as typed by the dispatcher, kept even when no vehicle matched",
        ),
    )


def downgrade() -> None:
    op.drop_column('dispatches', 'plate_raw')
