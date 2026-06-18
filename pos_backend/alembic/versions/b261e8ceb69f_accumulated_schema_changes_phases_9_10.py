"""accumulated_schema_changes_phases_9_10

Revision ID: b261e8ceb69f
Revises: 8c005ee89373
Create Date: 2026-06-12 09:53:03.782153
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b261e8ceb69f'
down_revision: Union[str, None] = '8c005ee89373'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── company_info: add columns missing from initial schema ──
    op.add_column('company_info', sa.Column('city', sa.String(length=100), nullable=True))
    op.add_column('company_info', sa.Column('province', sa.String(length=100), nullable=True))
    op.add_column('company_info', sa.Column('country', sa.String(length=100), nullable=True))
    op.add_column('company_info', sa.Column('fiscal_regime', sa.String(length=200), nullable=True))
    op.add_column('company_info', sa.Column('sri_environment', sa.Integer(), nullable=True,
              comment='1=PRUEBAS, 2=PRODUCCION'))
    op.add_column('company_info', sa.Column('emission_type', sa.Integer(), nullable=True,
              comment='1=NORMAL'))

    # ── dispatch_details: add columns missing from initial schema ──
    op.add_column('dispatch_details', sa.Column('price_without_subsidy',
              sa.NUMERIC(precision=10, scale=4), nullable=True,
              comment='unit_price + subsidy_per_unit at time of sale'))
    op.add_column('dispatch_details', sa.Column('subsidy_amount',
              sa.NUMERIC(precision=12, scale=2), nullable=True,
              comment='quantity × subsidy_per_unit at time of sale'))

    # ── dispatches: add columns missing from initial schema ──
    op.add_column('dispatches', sa.Column('access_key', sa.VARCHAR(length=49), nullable=True,
              comment='SRI access key (49 digits, computed at invoicing)'))
    op.add_column('dispatches', sa.Column('key49_invoice_id', sa.VARCHAR(length=36), nullable=True,
              comment='Key49 invoice UUID'))
    op.add_column('dispatches', sa.Column('key49_access_key', sa.VARCHAR(length=49), nullable=True,
              comment='Official SRI access key from Key49'))
    op.add_column('dispatches', sa.Column('sri_status', sa.VARCHAR(length=20), nullable=True,
              server_default=sa.text("'PENDING'::character varying"),
              comment='SRI status: PENDING, CREATED, SIGNED, SENT, AUTHORIZED, REJECTED, FAILED'))
    op.add_column('dispatches', sa.Column('sri_authorization_date',
              postgresql.TIMESTAMP(timezone=True), nullable=True,
              comment='When SRI authorized'))
    op.add_column('dispatches', sa.Column('sri_messages', sa.VARCHAR(length=500), nullable=True,
              comment='JSON array of SRI error messages if rejected'))
    op.add_column('dispatches', sa.Column('preset_value', sa.VARCHAR(length=20), nullable=True))
    op.add_column('dispatches', sa.Column('authorized_by_user_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_dispatches_authorized_by_user_id', 'dispatches', 'users',
              ['authorized_by_user_id'], ['user_id'])
    op.add_column('dispatches', sa.Column('hose_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_dispatches_hose_id', 'dispatches', 'hoses',
              ['hose_id'], ['hose_id'])
    op.add_column('dispatches', sa.Column('grade_id', sa.VARCHAR(length=20), nullable=True))

    # ── products: add column missing from initial schema ──
    op.add_column('products', sa.Column('subsidy_per_unit',
              sa.NUMERIC(precision=10, scale=4), nullable=True,
              comment='Government fuel subsidy per unit (e.g. per gallon)'))

    # ── vehicles: add columns missing from initial schema ──
    op.add_column('vehicles', sa.Column('billing_person_id', sa.Integer(), nullable=True,
              comment='Preferred billing person. NULL = use owner (person_id).'))
    op.add_column('vehicles', sa.Column('allow_container_sale', sa.Boolean(), nullable=False,
              server_default=sa.text('false'),
              comment='Allow this vehicle to be used when customer has no vehicle'))

    # ── payment_methods: add sri_code ──
    op.add_column('payment_methods', sa.Column('sri_code', sa.VARCHAR(length=3), nullable=False,
              server_default=sa.text("'20'::character varying")))

    # ── dispensers: add sort_order, drop fusion_pump_id (moved to hoses) ──
    op.add_column('dispensers', sa.Column('sort_order', sa.Integer(), nullable=False,
              server_default=sa.text('0')))
    op.drop_column('dispensers', 'fusion_pump_id')

    # ── shifts: add surplus/shortage for close-shift reconciliation ──
    op.add_column('shifts', sa.Column('surplus', sa.NUMERIC(precision=12, scale=2), nullable=True,
              server_default=sa.text('0')))
    op.add_column('shifts', sa.Column('shortage', sa.NUMERIC(precision=12, scale=2), nullable=True,
              server_default=sa.text('0')))

    # ── cash_movements: add TRANSFER_IN + DEPOSIT to check constraint ──
    op.drop_constraint('ck_cash_movements_type', 'cash_movements', type_='check')
    op.create_check_constraint('ck_cash_movements_type', 'cash_movements',
              "type IN ('INCOME', 'EXPENSE', 'SAFE_DROP', 'TRANSFER_OUT', 'TRANSFER_IN', 'DEPOSIT')")

    # ── persons: unique constraint on id_type + id_number ──
    op.create_unique_constraint('uq_persons_id_type_id_number', 'persons', ['id_type', 'id_number'])

    # ### end Alembic commands ###


def downgrade() -> None:
    # ── persons: drop unique constraint ──
    op.drop_constraint('uq_persons_id_type_id_number', 'persons', type_='unique')

    # ── cash_movements: restore original check constraint ──
    op.drop_constraint('ck_cash_movements_type', 'cash_movements', type_='check')
    op.create_check_constraint('ck_cash_movements_type', 'cash_movements',
              "type IN ('INCOME', 'EXPENSE', 'SAFE_DROP', 'TRANSFER_OUT')")

    # ── shifts: drop surplus/shortage ──
    op.drop_column('shifts', 'shortage')
    op.drop_column('shifts', 'surplus')

    # ── dispensers: restore fusion_pump_id, drop sort_order ──
    op.add_column('dispensers', sa.Column('fusion_pump_id', sa.Integer(), nullable=False,
              server_default=sa.text('0')))
    op.drop_column('dispensers', 'sort_order')

    # ── payment_methods ──
    op.drop_column('payment_methods', 'sri_code')

    # ── vehicles ──
    op.drop_column('vehicles', 'allow_container_sale')
    op.drop_column('vehicles', 'billing_person_id')

    # ── products ──
    op.drop_column('products', 'subsidy_per_unit')

    # ── dispatches ──
    op.drop_column('dispatches', 'grade_id')
    op.drop_constraint('fk_dispatches_hose_id', 'dispatches', type_='foreignkey')
    op.drop_column('dispatches', 'hose_id')
    op.drop_constraint('fk_dispatches_authorized_by_user_id', 'dispatches', type_='foreignkey')
    op.drop_column('dispatches', 'authorized_by_user_id')
    op.drop_column('dispatches', 'preset_value')
    op.drop_column('dispatches', 'sri_messages')
    op.drop_column('dispatches', 'sri_authorization_date')
    op.drop_column('dispatches', 'sri_status')
    op.drop_column('dispatches', 'key49_access_key')
    op.drop_column('dispatches', 'key49_invoice_id')
    op.drop_column('dispatches', 'access_key')

    # ── dispatch_details ──
    op.drop_column('dispatch_details', 'subsidy_amount')
    op.drop_column('dispatch_details', 'price_without_subsidy')

    # ── company_info ──
    op.drop_column('company_info', 'emission_type')
    op.drop_column('company_info', 'sri_environment')
    op.drop_column('company_info', 'fiscal_regime')
    op.drop_column('company_info', 'country')
    op.drop_column('company_info', 'province')
    op.drop_column('company_info', 'city')
    # ### end Alembic commands ###
