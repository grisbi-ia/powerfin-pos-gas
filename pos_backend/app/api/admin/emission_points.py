"""Admin emission points CRUD — SRI authorization points for invoicing."""

import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.deps import get_admin_user, require_permission
from app.database import get_db
from app.models.tributary import EmissionPoint
from app.models.user import User
from app.schemas import (
    AdminEmissionPointDetail,
    AdminEmissionPointListItem,
    CreateEmissionPointRequest,
    ErrorResponse,
    PaginatedResponse,
    UpdateEmissionPointRequest,
)

router = APIRouter(
    prefix="/api/admin/emission-points",
    tags=["admin-emission-points"],
    dependencies=[Depends(get_admin_user)],
)


# ── Helpers ────────────────────────────────────────────────────────


def _ep_to_label(ep: EmissionPoint) -> str:
    return f"{ep.establishment}-{ep.emission_point}"


def _ep_to_list_item(ep: EmissionPoint) -> dict:
    return {
        "emission_point_id": ep.emission_point_id,
        "establishment": ep.establishment,
        "emission_point": ep.emission_point,
        "label": _ep_to_label(ep),
        "doc_type": ep.doc_type,
        "current_sequential": ep.current_sequential,
        "is_active": ep.is_active,
    }


def _ep_to_detail(ep: EmissionPoint) -> dict:
    return {
        "emission_point_id": ep.emission_point_id,
        "establishment": ep.establishment,
        "emission_point": ep.emission_point,
        "label": _ep_to_label(ep),
        "doc_type": ep.doc_type,
        "current_sequential": ep.current_sequential,
        "sequential_start": ep.sequential_start,
        "sequential_end": ep.sequential_end,
        "authorization_number": ep.authorization_number,
        "authorization_date": ep.authorization_date,
        "authorization_expiry": ep.authorization_expiry,
        "is_active": ep.is_active,
    }


# ── Endpoints ──────────────────────────────────────────────────────


@router.get("", response_model=PaginatedResponse)
async def list_emission_points(
    search: str = Query("", description="Search by label, establishment, or emission_point"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = Query("establishment", pattern=r"^(establishment|emission_point|doc_type|is_active)$"),
    order: str = Query("asc", pattern=r"^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("emission_points", "read")),
):
    """List emission points with search, pagination, sorting."""
    base = select(EmissionPoint)
    count_q = select(func.count(EmissionPoint.emission_point_id))

    if search:
        pattern = f"%{search.strip()}%"
        from sqlalchemy import or_
        filter_clause = or_(
            EmissionPoint.establishment.like(pattern),
            EmissionPoint.emission_point.like(pattern),
            EmissionPoint.doc_type.like(f"%{search.strip().upper()}%"),
        )
        base = base.where(filter_clause)
        count_q = count_q.where(filter_clause)

    total = (await db.execute(count_q)).scalar() or 0
    pages = max(1, math.ceil(total / page_size))

    sort_col = getattr(EmissionPoint, sort, EmissionPoint.establishment)
    if order == "desc":
        sort_col = sort_col.desc()

    offset = (page - 1) * page_size
    result = await db.execute(base.order_by(sort_col).offset(offset).limit(page_size))
    eps = result.scalars().all()

    return PaginatedResponse(
        items=[_ep_to_list_item(ep) for ep in eps],
        total=total, page=page, page_size=page_size, pages=pages,
    )


@router.post(
    "",
    response_model=AdminEmissionPointDetail,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}},
)
async def create_emission_point(
    body: CreateEmissionPointRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("emission_points", "write")),
):
    """Create a new emission point. (establishment, emission_point) pair must be unique."""
    # Check uniqueness of the pair
    existing = (await db.execute(
        select(EmissionPoint).where(
            EmissionPoint.establishment == body.establishment,
            EmissionPoint.emission_point == body.emission_point,
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El punto de emisión {body.establishment}-{body.emission_point} ya existe",
        )

    ep = EmissionPoint(
        establishment=body.establishment,
        emission_point=body.emission_point,
        doc_type=body.doc_type,
        sequential_start=body.sequential_start,
        sequential_end=body.sequential_end,
        current_sequential=body.sequential_start,  # start at the beginning
        authorization_number=body.authorization_number,
        authorization_date=body.authorization_date,
        authorization_expiry=body.authorization_expiry,
    )
    db.add(ep)
    await db.commit()
    await db.refresh(ep)
    return _ep_to_detail(ep)


@router.get(
    "/{emission_point_id}",
    response_model=AdminEmissionPointDetail,
    responses={404: {"model": ErrorResponse}},
)
async def get_emission_point(
    emission_point_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("emission_points", "read")),
):
    """Get a single emission point by id."""
    ep = await db.get(EmissionPoint, emission_point_id)
    if not ep:
        raise HTTPException(status_code=404, detail="Punto de emisión no encontrado")
    return _ep_to_detail(ep)


@router.put(
    "/{emission_point_id}",
    response_model=AdminEmissionPointDetail,
    responses={404: {"model": ErrorResponse}},
)
async def update_emission_point(
    emission_point_id: int,
    body: UpdateEmissionPointRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("emission_points", "write")),
):
    """Update emission point fields. Only provided fields are changed.

    establishment and emission_point codes cannot be changed.
    Use is_active=False to deactivate.
    """
    ep = await db.get(EmissionPoint, emission_point_id)
    if not ep:
        raise HTTPException(status_code=404, detail="Punto de emisión no encontrado")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(ep, key):
            setattr(ep, key, value)

    await db.commit()
    await db.refresh(ep)
    return _ep_to_detail(ep)
