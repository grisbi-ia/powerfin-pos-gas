"""extend_plate_to_15_chars

Revision ID: 8fb50a8e8bad
Revises: 97eb95db805e
Create Date: 2026-07-08 09:19:25.116022
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8fb50a8e8bad'
down_revision: Union[str, None] = '97eb95db805e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('vehicles', 'plate',
               existing_type=sa.VARCHAR(length=10),
               type_=sa.String(length=15),
               existing_nullable=False)


def downgrade() -> None:
    op.alter_column('vehicles', 'plate',
               existing_type=sa.String(length=15),
               type_=sa.VARCHAR(length=10),
               existing_nullable=False)
