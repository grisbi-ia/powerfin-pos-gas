"""Admin grades CRUD — list, create, read, update, soft-delete.

Grades are fuel grades (Diesel, Super, Eco Plus, etc.) linked to products.
Soft-delete sets is_active=False — preserves referential integrity with hoses.
"""

import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.deps import get_admin_user, require_permission
from app.database import get_db
from app.models.product import Grade, Product
from app.models.user import User
from app.schemas import (
    AdminGradeDetail,
    AdminGradeListItem,
    CreateGradeRequest,
    ErrorResponse,
    PaginatedResponse,
    UpdateGradeRequest,
)

router = APIRouter(
    prefix="/api/admin/grades",
    tags=["admin-grades"],
    dependencies=[Depends(get_admin_user)],
)


# ── Helpers ────────────────────────────────────────────────────────


def _grade_to_list_item(grade: Grade, product: Product) -> dict:
    return {
        "grade_id": grade.grade_id,
        "code": grade.code,
        "name": grade.name,
        "product_id": grade.product_id,
        "product_name": product.name if product else "???",
        "product_code": product.code if product else "???",
        "is_active": grade.is_active,
    }


def _grade_to_detail(grade: Grade, product: Product) -> dict:
    return {
        "grade_id": grade.grade_id,
        "code": grade.code,
        "name": grade.name,
        "product_id": grade.product_id,
        "product_name": product.name if product else "???",
        "product_code": product.code if product else "???",
        "product_unit": product.unit if product else "???",
        "is_active": grade.is_active,
    }


# ── Endpoints ──────────────────────────────────────────────────────


@router.get("", response_model=PaginatedResponse)
async def list_grades(
    search: str = Query("", description="Search by name or code"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = Query("name", pattern=r"^(name|code|product_id|is_active)$"),
    order: str = Query("asc", pattern=r"^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("grades", "read")),
):
    """List fuel grades with search, pagination, and sorting."""
    base = select(Grade, Product).join(
        Product, Grade.product_id == Product.product_id, isouter=True
    )
    count_q = select(func.count(Grade.grade_id))

    if search:
        pattern = f"%{search.strip().lower()}%"
        from sqlalchemy import or_
        filter_clause = or_(
            func.lower(Grade.name).like(pattern),
            func.lower(Grade.code).like(pattern),
        )
        base = base.where(filter_clause)
        count_q = count_q.where(filter_clause)

    # Count
    total = (await db.execute(count_q)).scalar() or 0
    pages = max(1, math.ceil(total / page_size))

    # Sort
    sort_col = getattr(Grade, sort, Grade.name)
    if order == "desc":
        sort_col = sort_col.desc()

    # Fetch page
    offset = (page - 1) * page_size
    result = await db.execute(base.order_by(sort_col).offset(offset).limit(page_size))
    rows = result.all()

    return PaginatedResponse(
        items=[_grade_to_list_item(g, p) for g, p in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post(
    "",
    response_model=AdminGradeDetail,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}},
)
async def create_grade(
    body: CreateGradeRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("grades", "write")),
):
    """Create a new fuel grade. Code must be unique. Product must exist."""
    # Check code uniqueness
    existing = await db.execute(
        select(Grade).where(Grade.code == body.code.upper())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El grado '{body.code}' ya existe",
        )

    # Validate product exists
    product = await db.get(Product, body.product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Producto con id {body.product_id} no encontrado",
        )

    grade = Grade(
        code=body.code.upper(),
        name=body.name,
        product_id=body.product_id,
        is_active=body.is_active,
    )
    db.add(grade)
    await db.commit()
    await db.refresh(grade)

    # Re-fetch product for response (may have been mutated)
    product = await db.get(Product, grade.product_id)
    return _grade_to_detail(grade, product)


@router.get(
    "/{grade_id}",
    response_model=AdminGradeDetail,
    responses={404: {"model": ErrorResponse}},
)
async def get_grade(
    grade_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("grades", "read")),
):
    """Get a single grade by id, with linked product info."""
    grade = await db.get(Grade, grade_id)
    if not grade:
        raise HTTPException(status_code=404, detail="Grado no encontrado")

    product = await db.get(Product, grade.product_id)
    return _grade_to_detail(grade, product)


@router.put(
    "/{grade_id}",
    response_model=AdminGradeDetail,
    responses={404: {"model": ErrorResponse}},
)
async def update_grade(
    grade_id: int,
    body: UpdateGradeRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("grades", "write")),
):
    """Update grade fields. Only provided fields are changed.

    The grade code cannot be changed (stable identifier).
    Use is_active=False to deactivate.
    """
    grade = await db.get(Grade, grade_id)
    if not grade:
        raise HTTPException(status_code=404, detail="Grado no encontrado")

    update_data = body.model_dump(exclude_unset=True)

    # Validate FK if product_id is changing
    if "product_id" in update_data:
        product = await db.get(Product, update_data["product_id"])
        if not product:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Producto con id {update_data['product_id']} no encontrado",
            )

    for key, value in update_data.items():
        if hasattr(grade, key):
            setattr(grade, key, value)

    await db.commit()
    await db.refresh(grade)

    product = await db.get(Product, grade.product_id)
    return _grade_to_detail(grade, product)


@router.delete(
    "/{grade_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
async def delete_grade(
    grade_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("grades", "delete")),
):
    """Soft-delete a grade (sets is_active=False).

    Hoses reference grades by code, so soft-delete preserves those references.
    """
    grade = await db.get(Grade, grade_id)
    if not grade:
        raise HTTPException(status_code=404, detail="Grado no encontrado")

    grade.is_active = False
    await db.commit()
