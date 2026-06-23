"""Admin dispensers + hoses CRUD.

Dispensers are physical pump units with one or two sides (hoses).
Each hose maps to a Fusion pump/hose ID and a fuel grade.
"""

import math

import httpx

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.admin.deps import get_admin_user, require_permission
from app.database import get_db
from app.models.company import SystemConfig
from app.models.dispenser import Dispenser, Hose
from app.models.product import Grade
from app.models.tributary import EmissionPoint
from app.models.user import User
from app.schemas import (
    AdminDispenserDetail,
    AdminDispenserHoseDetail,
    AdminDispenserListItem,
    CreateDispenserRequest,
    CreateHoseRequest,
    ErrorResponse,
    PaginatedResponse,
    UpdateDispenserRequest,
    UpdateHoseRequest,
)

router = APIRouter(
    prefix="/api/admin",
    tags=["admin-dispensers"],
    dependencies=[Depends(get_admin_user)],
)


# ── Emission Point Helpers ─────────────────────────────────────────


async def _emission_label(db: AsyncSession, ep_id: int | None) -> str | None:
    if not ep_id:
        return None
    ep = await db.get(EmissionPoint, ep_id)
    return f"{ep.establishment}-{ep.emission_point}" if ep else None


# ── Hose Helpers ───────────────────────────────────────────────────


async def _hose_to_detail(h: Hose, db: AsyncSession) -> dict:
    """Build a hose detail dict with grade name."""
    grade_name = h.grade_id  # fallback to code
    grade = (await db.execute(
        select(Grade).where(Grade.code == h.grade_id)
    )).scalar_one_or_none()
    if grade:
        grade_name = grade.name

    return {
        "hose_id": h.hose_id,
        "side": h.side,
        "fusion_pump_id": h.fusion_pump_id,
        "fusion_hose_id": h.fusion_hose_id,
        "grade_code": h.grade_id,
        "grade_name": grade_name,
        "is_active": h.is_active,
    }


async def _get_hose_or_404(dispenser_id: int, hose_id: int, db: AsyncSession) -> Hose:
    result = await db.execute(
        select(Hose).where(
            Hose.hose_id == hose_id,
            Hose.dispenser_id == dispenser_id,
        )
    )
    hose = result.scalar_one_or_none()
    if not hose:
        raise HTTPException(status_code=404, detail="Manguera no encontrada")
    return hose


# ── Dispenser CRUD ─────────────────────────────────────────────────


@router.get("/dispensers", response_model=PaginatedResponse)
async def list_dispensers(
    search: str = Query("", description="Search by name or code"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = Query("sort_order", pattern=r"^(name|code|sort_order|is_active)$"),
    order: str = Query("asc", pattern=r"^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dispensers", "read")),
):
    """List dispensers with search, pagination, sorting. Loads hoses for count."""
    base = select(Dispenser).options(selectinload(Dispenser.hoses))
    count_q = select(func.count(Dispenser.dispenser_id))

    if search:
        pattern = f"%{search.strip().lower()}%"
        from sqlalchemy import or_
        filter_clause = or_(
            func.lower(Dispenser.name).like(pattern),
            func.lower(Dispenser.code).like(pattern),
        )
        base = base.where(filter_clause)
        count_q = count_q.where(filter_clause)

    total = (await db.execute(count_q)).scalar() or 0
    pages = max(1, math.ceil(total / page_size))

    sort_col = getattr(Dispenser, sort, Dispenser.sort_order)
    if order == "desc":
        sort_col = sort_col.desc()

    offset = (page - 1) * page_size
    result = await db.execute(base.order_by(sort_col).offset(offset).limit(page_size))
    dispensers = result.unique().scalars().all()

    items = []
    for d in dispensers:
        items.append({
            "dispenser_id": d.dispenser_id,
            "code": d.code,
            "name": d.name,
            "emission_point_label": await _emission_label(db, d.emission_point_id),
            "printer_ip": d.printer_ip,
            "printer_port": d.printer_port,
            "hose_count": len([h for h in d.hoses if h.is_active]),
            "sort_order": d.sort_order,
            "is_active": d.is_active,
        })

    return PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size, pages=pages,
    )


@router.post(
    "/dispensers",
    response_model=AdminDispenserDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_dispenser(
    body: CreateDispenserRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dispensers", "write")),
):
    """Create a new dispenser."""
    # Validate emission point if provided
    if body.emission_point_id is not None:
        ep = await db.get(EmissionPoint, body.emission_point_id)
        if not ep:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Punto de emisión con id {body.emission_point_id} no encontrado",
            )

    d = Dispenser(
        code=body.code.upper(),
        name=body.name,
        emission_point_id=body.emission_point_id,
        printer_ip=body.printer_ip,
        printer_port=body.printer_port,
        sort_order=body.sort_order,
    )
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return await _dispenser_to_detail(d, db)


async def _dispenser_to_detail(d: Dispenser, db: AsyncSession) -> dict:
    """Build dispenser detail with hoses and emission point label."""
    # Re-fetch with hoses eager-loaded
    result = await db.execute(
        select(Dispenser)
        .where(Dispenser.dispenser_id == d.dispenser_id)
        .options(selectinload(Dispenser.hoses))
    )
    d = result.scalar_one()

    hoses = []
    for h in d.hoses:
        hoses.append(await _hose_to_detail(h, db))

    return {
        "dispenser_id": d.dispenser_id,
        "code": d.code,
        "name": d.name,
        "emission_point_id": d.emission_point_id,
        "emission_point_label": await _emission_label(db, d.emission_point_id),
        "printer_ip": d.printer_ip,
        "printer_port": d.printer_port,
        "sort_order": d.sort_order,
        "is_active": d.is_active,
        "hoses": hoses,
    }


# ── Live Status ────────────────────────────────────────────────────


@router.get("/dispensers/status")
async def dispenser_live_status(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dispensers", "read")),
):
    """Get live dispenser status from FusionBridge, enriched with DB names."""
    # FusionBridge URL — default localhost, overridable via system_config
    bridge_url = "http://localhost:8090"
    cfg = await db.execute(
        select(SystemConfig).where(SystemConfig.key == "fusion_bridge_url")
    )
    cfg_row = cfg.scalar_one_or_none()
    if cfg_row and cfg_row.value:
        bridge_url = cfg_row.value.rstrip("/")

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            resp = await client.get(f"{bridge_url}/api/dispensers")
            resp.raise_for_status()
            fusion_data = resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=502, detail="FusionBridge no responde (timeout 5s)")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Error de FusionBridge: {e}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"FusionBridge no accesible: {str(e)}")

    fusion_connected = fusion_data.get("fusionConnected", False)
    fusion_dispensers = fusion_data.get("dispensers", [])

    result = await db.execute(
        select(Dispenser).options(selectinload(Dispenser.hoses))
    )
    db_dispensers: dict[int, Dispenser] = {d.dispenser_id: d for d in result.scalars()}

    pump_to_disp: dict[int, Dispenser] = {}
    for d in db_dispensers.values():
        for h in d.hoses:
            if h.fusion_pump_id:
                pump_to_disp[h.fusion_pump_id] = d
                break

    enriched = []
    for fd in fusion_dispensers:
        fusion_pump_id: int = fd.get("dispenserId", 0)
        status_val: str = fd.get("status", "UNKNOWN")
        connected: bool = fd.get("connected", False)
        preset_amount: float = fd.get("presetAmount", 0.0)
        active_hose: int = fd.get("activeHose", 0)

        db_disp = pump_to_disp.get(fusion_pump_id)

        # Skip Fusion pumps not mapped to any DB dispenser (e.g. pumps 5-8 if only 4 configured)
        if not db_disp:
            continue

        # Build hose info from DB
        hoses_data: list[dict] = []
        for h in sorted(db_disp.hoses, key=lambda x: x.side or ""):
            active = (h.fusion_hose_id == active_hose) if active_hose > 0 else False
            hoses_data.append({
                "side": h.side or "?",
                "grade": h.grade_id or "",
                "active": active,
            })

        enriched.append({
            "dispenser_id": db_disp.dispenser_id,
            "name": db_disp.name,
            "status": status_val,
            "connected": connected,
            "preset_amount": preset_amount,
            "hoses": hoses_data,
        })

    enriched.sort(key=lambda d: d["dispenser_id"])

    return {
        "dispensers": enriched,
        "fusion_connected": fusion_connected,
    }


@router.get(
    "/dispensers/{dispenser_id}",
    response_model=AdminDispenserDetail,
    responses={404: {"model": ErrorResponse}},
)
async def get_dispenser(
    dispenser_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dispensers", "read")),
):
    """Get a dispenser with all its hoses and emission point info."""
    result = await db.execute(
        select(Dispenser)
        .where(Dispenser.dispenser_id == dispenser_id)
        .options(selectinload(Dispenser.hoses))
    )
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Dispensador no encontrado")
    return await _dispenser_to_detail(d, db)


@router.put(
    "/dispensers/{dispenser_id}",
    response_model=AdminDispenserDetail,
    responses={404: {"model": ErrorResponse}},
)
async def update_dispenser(
    dispenser_id: int,
    body: UpdateDispenserRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dispensers", "write")),
):
    """Update dispenser fields. Only provided fields are changed."""
    d = await db.get(Dispenser, dispenser_id)
    if not d:
        raise HTTPException(status_code=404, detail="Dispensador no encontrado")

    update_data = body.model_dump(exclude_unset=True)

    # Validate emission_point_id if changing
    if "emission_point_id" in update_data and update_data["emission_point_id"] is not None:
        ep = await db.get(EmissionPoint, update_data["emission_point_id"])
        if not ep:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Punto de emisión con id {update_data['emission_point_id']} no encontrado",
            )

    for key, value in update_data.items():
        if hasattr(d, key):
            setattr(d, key, value)

    await db.commit()
    await db.refresh(d)
    return await _dispenser_to_detail(d, db)


@router.delete(
    "/dispensers/{dispenser_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
async def delete_dispenser(
    dispenser_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dispensers", "delete")),
):
    """Soft-delete a dispenser (sets is_active=False)."""
    d = await db.get(Dispenser, dispenser_id)
    if not d:
        raise HTTPException(status_code=404, detail="Dispensador no encontrado")

    d.is_active = False
    await db.commit()


# ── Hose CRUD (nested under dispensers) ────────────────────────────


@router.get(
    "/dispensers/{dispenser_id}/hoses",
    response_model=list[AdminDispenserHoseDetail],
)
async def list_hoses(
    dispenser_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dispensers", "read")),
):
    """List all hoses for a dispenser."""
    d = await db.get(Dispenser, dispenser_id)
    if not d:
        raise HTTPException(status_code=404, detail="Dispensador no encontrado")

    result = await db.execute(
        select(Hose)
        .where(Hose.dispenser_id == dispenser_id)
        .order_by(Hose.side)
    )
    hoses = result.scalars().all()
    return [await _hose_to_detail(h, db) for h in hoses]


@router.post(
    "/dispensers/{dispenser_id}/hoses",
    response_model=AdminDispenserHoseDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_hose(
    dispenser_id: int,
    body: CreateHoseRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dispensers", "write")),
):
    """Add a hose to a dispenser."""
    d = await db.get(Dispenser, dispenser_id)
    if not d:
        raise HTTPException(status_code=404, detail="Dispensador no encontrado")

    # Check side uniqueness within the dispenser (active hoses only)
    existing = (await db.execute(
        select(Hose).where(
            Hose.dispenser_id == dispenser_id,
            Hose.side == body.side,
            Hose.is_active == True,
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El lado {body.side} ya tiene una manguera activa en este dispensador",
        )

    # Validate grade exists (by code)
    grade = (await db.execute(
        select(Grade).where(Grade.code == body.grade_code.upper())
    )).scalar_one_or_none()

    h = Hose(
        dispenser_id=dispenser_id,
        side=body.side,
        fusion_pump_id=body.fusion_pump_id,
        fusion_hose_id=body.fusion_hose_id,
        grade_id=body.grade_code.upper() if grade else body.grade_code,
    )
    db.add(h)
    await db.commit()
    await db.refresh(h)
    return await _hose_to_detail(h, db)


@router.put(
    "/dispensers/{dispenser_id}/hoses/{hose_id}",
    response_model=AdminDispenserHoseDetail,
    responses={404: {"model": ErrorResponse}},
)
async def update_hose(
    dispenser_id: int,
    hose_id: int,
    body: UpdateHoseRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dispensers", "write")),
):
    """Update a hose's grade, Fusion IDs, or active status."""
    h = await _get_hose_or_404(dispenser_id, hose_id, db)

    update_data = body.model_dump(exclude_unset=True)

    # Normalize grade_code if provided
    if "grade_code" in update_data and update_data["grade_code"] is not None:
        grade = (await db.execute(
            select(Grade).where(Grade.code == update_data["grade_code"].upper())
        )).scalar_one_or_none()
        update_data["grade_id"] = update_data["grade_code"].upper() if grade else update_data["grade_code"]
        del update_data["grade_code"]

    for key, value in update_data.items():
        if hasattr(h, key):
            setattr(h, key, value)

    await db.commit()
    await db.refresh(h)
    return await _hose_to_detail(h, db)
