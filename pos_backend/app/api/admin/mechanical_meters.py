"""Admin CRUD for mechanical meters (nested under dispensers).

Mechanical meters are physical flow counters on dispensers.
Each meter maps either to a product (PRODUCT type) or a hose (HOSE type).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.admin.deps import get_admin_user, require_permission
from app.database import get_db
from app.models.dispenser import Dispenser, Hose
from app.models.mechanical_meter import MechanicalMeter
from app.models.product import Grade
from app.models.user import User
from app.schemas import (
    CreateMechanicalMeterRequest,
    ErrorResponse,
    MechanicalMeterResponse,
    UpdateMechanicalMeterRequest,
)

router = APIRouter(
    prefix="/api/admin",
    tags=["admin-mechanical-meters"],
    dependencies=[Depends(get_admin_user)],
)


async def _meter_to_response(m: MechanicalMeter, db: AsyncSession) -> MechanicalMeterResponse:
    """Build a MechanicalMeterResponse with resolved FK labels."""
    grade_code = None
    grade_name = None
    hose_side = None

    if m.meter_type == "PRODUCT" and m.grade_id:
        grade = await db.get(Grade, m.grade_id)
        if grade:
            grade_code = grade.code
            grade_name = grade.name

    if m.meter_type == "HOSE" and m.hose_id:
        hose = await db.get(Hose, m.hose_id)
        if hose:
            hose_side = hose.side
            # Also resolve the grade through the hose
            grade_code = hose.grade_id
            grade_result = await db.execute(
                select(Grade).where(Grade.code == hose.grade_id)
            )
            g = grade_result.scalar_one_or_none()
            if g:
                grade_name = g.name

    return MechanicalMeterResponse(
        meter_id=m.meter_id,
        dispenser_id=m.dispenser_id,
        name=m.name,
        meter_type=m.meter_type,
        grade_id=m.grade_id,
        grade_code=grade_code,
        grade_name=grade_name,
        hose_id=m.hose_id,
        hose_side=hose_side,
        sort_order=m.sort_order,
        is_active=m.is_active,
    )


# ── List ───────────────────────────────────────────────────────────


@router.get(
    "/dispensers/{dispenser_id}/meters",
    response_model=list[MechanicalMeterResponse],
)
async def list_meters(
    dispenser_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dispensers", "read")),
):
    """List all mechanical meters for a dispenser."""
    d = await db.get(Dispenser, dispenser_id)
    if not d:
        raise HTTPException(status_code=404, detail="Dispensador no encontrado")

    result = await db.execute(
        select(MechanicalMeter)
        .where(MechanicalMeter.dispenser_id == dispenser_id)
        .order_by(MechanicalMeter.sort_order, MechanicalMeter.meter_id)
    )
    meters = result.scalars().all()
    return [await _meter_to_response(m, db) for m in meters]


# ── Create ─────────────────────────────────────────────────────────


@router.post(
    "/dispensers/{dispenser_id}/meters",
    response_model=MechanicalMeterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_meter(
    dispenser_id: int,
    body: CreateMechanicalMeterRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dispensers", "write")),
):
    """Add a mechanical meter to a dispenser."""
    d = await db.get(Dispenser, dispenser_id)
    if not d:
        raise HTTPException(status_code=404, detail="Dispensador no encontrado")

    # Validate FK references
    if body.meter_type == "PRODUCT" and body.grade_id:
        grade = await db.get(Grade, body.grade_id)
        if not grade:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Grado con id {body.grade_id} no encontrado",
            )

    if body.meter_type == "HOSE" and body.hose_id:
        hose = await db.get(Hose, body.hose_id)
        if not hose:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Manguera con id {body.hose_id} no encontrada",
            )
        # Verify hose belongs to this dispenser
        if hose.dispenser_id != dispenser_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La manguera {body.hose_id} no pertenece al dispensador {dispenser_id}",
            )

    m = MechanicalMeter(
        dispenser_id=dispenser_id,
        name=body.name,
        meter_type=body.meter_type,
        grade_id=body.grade_id if body.meter_type == "PRODUCT" else None,
        hose_id=body.hose_id if body.meter_type == "HOSE" else None,
        sort_order=body.sort_order,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return await _meter_to_response(m, db)


# ── Update ─────────────────────────────────────────────────────────


@router.put(
    "/dispensers/{dispenser_id}/meters/{meter_id}",
    response_model=MechanicalMeterResponse,
    responses={404: {"model": ErrorResponse}},
)
async def update_meter(
    dispenser_id: int,
    meter_id: int,
    body: UpdateMechanicalMeterRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dispensers", "write")),
):
    """Update a mechanical meter. meter_type is immutable."""
    result = await db.execute(
        select(MechanicalMeter).where(
            MechanicalMeter.meter_id == meter_id,
            MechanicalMeter.dispenser_id == dispenser_id,
        )
    )
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Medidor no encontrado")

    update_data = body.model_dump(exclude_unset=True)

    # Handle FK changes
    if "grade_id" in update_data:
        if m.meter_type != "PRODUCT" and update_data["grade_id"] is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo medidores tipo PRODUCT pueden tener grade_id",
            )
        if update_data["grade_id"] is not None:
            grade = await db.get(Grade, update_data["grade_id"])
            if not grade:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Grado con id {update_data['grade_id']} no encontrado",
                )

    if "hose_id" in update_data:
        if m.meter_type != "HOSE" and update_data["hose_id"] is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo medidores tipo HOSE pueden tener hose_id",
            )
        if update_data["hose_id"] is not None:
            hose = await db.get(Hose, update_data["hose_id"])
            if not hose:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Manguera con id {update_data['hose_id']} no encontrada",
                )
            if hose.dispenser_id != dispenser_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"La manguera {update_data['hose_id']} no pertenece al dispensador {dispenser_id}",
                )

    for key, value in update_data.items():
        if hasattr(m, key):
            setattr(m, key, value)

    await db.commit()
    await db.refresh(m)
    return await _meter_to_response(m, db)


# ── Delete (soft) ──────────────────────────────────────────────────


@router.delete(
    "/dispensers/{dispenser_id}/meters/{meter_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
async def delete_meter(
    dispenser_id: int,
    meter_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dispensers", "delete")),
):
    """Soft-delete a mechanical meter (sets is_active=False)."""
    result = await db.execute(
        select(MechanicalMeter).where(
            MechanicalMeter.meter_id == meter_id,
            MechanicalMeter.dispenser_id == dispenser_id,
        )
    )
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Medidor no encontrado")

    m.is_active = False
    await db.commit()
