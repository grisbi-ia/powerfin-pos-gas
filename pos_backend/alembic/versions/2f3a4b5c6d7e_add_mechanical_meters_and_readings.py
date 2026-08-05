"""add_mechanical_meters_and_readings

Revision ID: 2f3a4b5c6d7e
Revises: 8fb50a8e8bad
Create Date: 2026-07-10 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2f3a4b5c6d7e'
down_revision: Union[str, None] = '8fb50a8e8bad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # mechanical_meters — configurable physical meter mapping per dispenser
    op.create_table(
        'mechanical_meters',
        sa.Column('meter_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('dispenser_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('meter_type', sa.String(20), nullable=False),
        sa.Column('grade_id', sa.Integer(), nullable=True),
        sa.Column('hose_id', sa.Integer(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.PrimaryKeyConstraint('meter_id'),
        sa.ForeignKeyConstraint(['dispenser_id'], ['dispensers.dispenser_id'],
                                name='fk_meters_dispenser'),
        sa.ForeignKeyConstraint(['grade_id'], ['grades.grade_id'],
                                name='fk_meters_grade'),
        sa.ForeignKeyConstraint(['hose_id'], ['hoses.hose_id'],
                                name='fk_meters_hose'),
        sa.CheckConstraint(
            "(meter_type = 'PRODUCT' AND grade_id IS NOT NULL AND hose_id IS NULL) OR "
            "(meter_type = 'HOSE' AND hose_id IS NOT NULL AND grade_id IS NULL)",
            name='ck_meter_mapping'
        ),
        sa.CheckConstraint(
            "meter_type IN ('PRODUCT', 'HOSE')",
            name='ck_meter_type'
        ),
    )
    op.create_index('ix_mechanical_meters_dispenser', 'mechanical_meters',
                    ['dispenser_id'])

    # meter_readings — per-shift opening/closing readings
    op.create_table(
        'meter_readings',
        sa.Column('reading_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('meter_id', sa.Integer(), nullable=False),
        sa.Column('shift_id', sa.Integer(), nullable=False),
        sa.Column('reading_type', sa.String(10), nullable=False),
        sa.Column('reading_value', sa.Numeric(12, 2), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('recorded_by', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('reading_id'),
        sa.ForeignKeyConstraint(['meter_id'], ['mechanical_meters.meter_id'],
                                name='fk_readings_meter'),
        sa.ForeignKeyConstraint(['shift_id'], ['shifts.shift_id'],
                                name='fk_readings_shift'),
        sa.ForeignKeyConstraint(['recorded_by'], ['users.user_id'],
                                name='fk_readings_user'),
        sa.CheckConstraint(
            "reading_type IN ('OPENING', 'CLOSING')",
            name='ck_reading_type'
        ),
        sa.UniqueConstraint('meter_id', 'shift_id', 'reading_type',
                            name='uq_reading_meter_shift_type'),
    )
    op.create_index('ix_meter_readings_shift', 'meter_readings', ['shift_id'])


def downgrade() -> None:
    op.drop_table('meter_readings')
    op.drop_table('mechanical_meters')
