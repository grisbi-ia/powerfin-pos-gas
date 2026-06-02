"""Atomic sequential number consumption for SRI emission points."""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tributary import EmissionPoint


class SequentialExhaustedError(Exception):
    """Raised when an emission point has no remaining sequential numbers."""


async def consume_sequential(
    db: AsyncSession, emission_point_id: int
) -> str:
    """
    Atomically consume the next sequential number from an emission point.

    Uses SELECT ... FOR UPDATE to guarantee uniqueness across concurrent
    transactions. Returns the formatted sequential string (e.g., '001-001-000000045').

    Raises SequentialExhaustedError if no numbers remain.
    """
    result = await db.execute(
        select(EmissionPoint)
        .where(EmissionPoint.emission_point_id == emission_point_id)
        .with_for_update()
    )
    ep = result.scalar_one_or_none()
    if ep is None:
        raise ValueError(f"Emission point {emission_point_id} not found")

    if ep.current_sequential > ep.sequential_end:
        raise SequentialExhaustedError(
            f"Secuencial agotado para {ep.establishment}-{ep.emission_point}. "
            f"Rango: {ep.sequential_start}-{ep.sequential_end}. "
            f"Renovar autorización SRI."
        )

    seq = ep.current_sequential
    await db.execute(
        update(EmissionPoint)
        .where(EmissionPoint.emission_point_id == emission_point_id)
        .values(current_sequential=ep.current_sequential + 1)
    )

    return f"{ep.establishment}-{ep.emission_point}-{seq:09d}"
