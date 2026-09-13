"""make persons.id_number nullable

Revision ID: 5c6d7e8f9a01
Revises: 4b5c6d7e8f90
Create Date: 2026-09-13 19:10:00.000000

A person may now exist **without a validated identification**. That is the
explicit "identification not verified yet" state: when a recorded cédula/RUC
turns out to be invalid (Key49 rejects it with "Invalid identification"), the
number is cleared instead of being kept wrong, so the POS is forced to ask the
customer for it again before the next sale.

* `id_type` stays NOT NULL (it records the expected kind of document).
* The UNIQUE (id_type, id_number) constraint is kept: PostgreSQL allows
  multiple NULLs, so any number of un-identified persons can coexist.
* Additive and non-breaking: existing rows are untouched.

Reversible: downgrade fails loudly if a NULL id_number still exists (data
would be lost by re-adding NOT NULL).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c6d7e8f9a01'
down_revision: Union[str, None] = '4b5c6d7e8f90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'persons',
        'id_number',
        existing_type=sa.String(length=13),
        nullable=True,
        comment=(
            "Validated identification. NULL = cleared because the recorded "
            "number was invalid; the POS must re-capture it (see "
            "app/services/id_validation.py)."
        ),
    )


def downgrade() -> None:
    # Fail loudly instead of silently dropping data.
    bind = op.get_bind()
    pending = bind.execute(
        sa.text("SELECT count(*) FROM persons WHERE id_number IS NULL")
    ).scalar()
    if pending:
        raise RuntimeError(
            f"Cannot downgrade: {pending} persons have id_number = NULL. "
            "Re-capture their identification first."
        )
    op.alter_column(
        'persons',
        'id_number',
        existing_type=sa.String(length=13),
        nullable=False,
        comment=None,
    )
