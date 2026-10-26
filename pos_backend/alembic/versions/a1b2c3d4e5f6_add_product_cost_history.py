"""add product cost history and dispatch detail unit cost

Revision ID: a1b2c3d4e5f6
Revises: 5c6d7e8f9a01
Create Date: 2026-10-26 09:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '5c6d7e8f9a01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'product_cost_history',
        sa.Column('product_cost_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('valid_from', sa.Date(), nullable=False),
        sa.Column('cost_price', sa.Numeric(10, 4), nullable=False),
        sa.Column('source', sa.String(20), server_default='MANUAL', nullable=False),
        sa.Column('notes', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['products.product_id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.user_id']),
        sa.PrimaryKeyConstraint('product_cost_id'),
        sa.UniqueConstraint('product_id', 'valid_from', name='uq_product_cost_valid_from'),
    )
    op.create_index(
        'ix_product_cost_history_product_valid_from',
        'product_cost_history',
        ['product_id', 'valid_from'],
    )

    op.add_column(
        'dispatch_details',
        sa.Column(
            'unit_cost',
            sa.Numeric(10, 4),
            nullable=True,
            comment='Purchase cost per unit (net of VAT) frozen at sale time',
        ),
    )


def downgrade() -> None:
    op.drop_column('dispatch_details', 'unit_cost')
    op.drop_index('ix_product_cost_history_product_valid_from', table_name='product_cost_history')
    op.drop_table('product_cost_history')
