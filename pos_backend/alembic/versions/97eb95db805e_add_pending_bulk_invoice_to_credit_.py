"""add_pending_bulk_invoice_to_credit_status

Revision ID: 97eb95db805e
Revises: 2e2a37a14335
Create Date: 2026-07-07 20:24:07.979547
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '97eb95db805e'
down_revision: Union[str, None] = '2e2a37a14335'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old constraint first so backfill can write new values
    op.drop_constraint('ck_dispatches_credit_status', 'dispatches', type_='check')
    # Backfill: rename PENDING_INVOICE → PENDING_PAYMENT
    op.execute(
        "UPDATE dispatches SET credit_status = 'PENDING_PAYMENT' "
        "WHERE credit_status = 'PENDING_INVOICE'"
    )
    # Create new constraint with expanded values
    op.create_check_constraint(
        'ck_dispatches_credit_status', 'dispatches',
        "credit_status IS NULL OR credit_status IN ('PENDING_PAYMENT', 'PENDING_BULK_INVOICE', 'INVOICED')"
    )


def downgrade() -> None:
    # Drop constraint so backfill can write old values
    op.drop_constraint('ck_dispatches_credit_status', 'dispatches', type_='check')
    # Revert data back to old name
    op.execute(
        "UPDATE dispatches SET credit_status = 'PENDING_INVOICE' "
        "WHERE credit_status = 'PENDING_PAYMENT'"
    )
    # Restore original constraint
    op.create_check_constraint(
        'ck_dispatches_credit_status', 'dispatches',
        "credit_status IS NULL OR credit_status IN ('PENDING_INVOICE', 'INVOICED')"
    )
