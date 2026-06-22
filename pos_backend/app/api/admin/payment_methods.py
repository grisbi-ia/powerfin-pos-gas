"""Admin payment methods CRUD — list, create, read, update."""

import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.deps import get_admin_user, require_permission
from app.database import get_db
from app.models.payment import PaymentMethod
from app.models.user import User
from app.schemas import (
    AdminPaymentMethodDetail,
    AdminPaymentMethodListItem,
    CreatePaymentMethodRequest,
    ErrorResponse,
    PaginatedResponse,
    UpdatePaymentMethodRequest,
)

router = APIRouter(
    prefix="/api/admin/payment-methods",
    tags=["admin-payment-methods"],
    dependencies=[Depends(get_admin_user)],
)


def _pm_to_dict(pm: PaymentMethod) -> dict:
    return {
        "payment_method_id": pm.payment_method_id,
        "code": pm.code,
        "name": pm.name,
        "sri_code": pm.sri_code,
        "requires_reference": pm.requires_reference,
        "is_active": pm.is_active,
    }


@router.get("", response_model=PaginatedResponse)
async def list_payment_methods(
    search: str = Query("", description="Search by name or code"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = Query("name", pattern=r"^(name|code|sri_code|is_active)$"),
    order: str = Query("asc", pattern=r"^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("payment_methods", "read")),
):
    base = select(PaymentMethod)
    count_q = select(func.count(PaymentMethod.payment_method_id))

    if search:
        pattern = f"%{search.strip().lower()}%"
        from sqlalchemy import or_
        filter_clause = or_(
            func.lower(PaymentMethod.name).like(pattern),
            func.lower(PaymentMethod.code).like(pattern),
        )
        base = base.where(filter_clause)
        count_q = count_q.where(filter_clause)

    total = (await db.execute(count_q)).scalar() or 0
    pages = max(1, math.ceil(total / page_size))

    sort_col = getattr(PaymentMethod, sort, PaymentMethod.name)
    if order == "desc":
        sort_col = sort_col.desc()

    offset = (page - 1) * page_size
    result = await db.execute(base.order_by(sort_col).offset(offset).limit(page_size))
    pms = result.scalars().all()

    return PaginatedResponse(
        items=[_pm_to_dict(pm) for pm in pms],
        total=total, page=page, page_size=page_size, pages=pages,
    )


@router.post(
    "",
    response_model=AdminPaymentMethodDetail,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}},
)
async def create_payment_method(
    body: CreatePaymentMethodRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("payment_methods", "write")),
):
    existing = await db.execute(
        select(PaymentMethod).where(PaymentMethod.code == body.code.upper())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"El método de pago '{body.code}' ya existe")

    pm = PaymentMethod(
        code=body.code.upper(),
        name=body.name,
        sri_code=body.sri_code,
        requires_reference=body.requires_reference,
        is_active=body.is_active,
    )
    db.add(pm)
    await db.commit()
    await db.refresh(pm)
    return _pm_to_dict(pm)


@router.get(
    "/{payment_method_id}",
    response_model=AdminPaymentMethodDetail,
    responses={404: {"model": ErrorResponse}},
)
async def get_payment_method(
    payment_method_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("payment_methods", "read")),
):
    pm = await db.get(PaymentMethod, payment_method_id)
    if not pm:
        raise HTTPException(status_code=404, detail="Método de pago no encontrado")
    return _pm_to_dict(pm)


@router.put(
    "/{payment_method_id}",
    response_model=AdminPaymentMethodDetail,
    responses={404: {"model": ErrorResponse}},
)
async def update_payment_method(
    payment_method_id: int,
    body: UpdatePaymentMethodRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("payment_methods", "write")),
):
    pm = await db.get(PaymentMethod, payment_method_id)
    if not pm:
        raise HTTPException(status_code=404, detail="Método de pago no encontrado")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(pm, key):
            setattr(pm, key, value)

    await db.commit()
    await db.refresh(pm)
    return _pm_to_dict(pm)
