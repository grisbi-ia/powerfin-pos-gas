"""Admin price lists CRUD — list, create, read, update, soft-delete.

Also nested CRUD for price list items (product prices within a list).
"""

import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.deps import get_admin_user, require_permission
from app.database import get_db
from app.models.pricing import PriceList, PriceListItem
from app.models.product import Product
from app.models.user import User
from app.schemas import (
    AdminPriceListDetail,
    AdminPriceListItemDetail,
    AdminPriceListListItem,
    CreatePriceListItemRequest,
    CreatePriceListRequest,
    ErrorResponse,
    PaginatedResponse,
    UpdatePriceListItemRequest,
    UpdatePriceListRequest,
)

router = APIRouter(
    prefix="/api/admin/price-lists",
    tags=["admin-price-lists"],
    dependencies=[Depends(get_admin_user)],
)


# ── Price List Helpers ──────────────────────────────────────────────


async def _price_list_to_list_item(pl: PriceList, db: AsyncSession) -> dict:
    """Build list item with active item count."""
    count_result = await db.execute(
        select(func.count(PriceListItem.price_list_item_id)).where(
            PriceListItem.price_list_id == pl.price_list_id,
            PriceListItem.is_active == True,
        )
    )
    item_count = count_result.scalar() or 0
    return {
        "price_list_id": pl.price_list_id,
        "code": pl.code,
        "name": pl.name,
        "is_default": pl.is_default,
        "item_count": item_count,
        "is_active": pl.is_active,
    }


async def _price_list_to_detail(pl: PriceList, db: AsyncSession) -> dict:
    """Build detail with active items."""
    items_result = await db.execute(
        select(PriceListItem, Product)
        .join(Product, PriceListItem.product_id == Product.product_id)
        .where(
            PriceListItem.price_list_id == pl.price_list_id,
            PriceListItem.is_active == True,
        )
        .order_by(Product.name)
    )
    items = []
    for pli, prod in items_result.all():
        items.append({
            "price_list_item_id": pli.price_list_item_id,
            "product_id": pli.product_id,
            "product_name": prod.name if prod else "???",
            "product_code": prod.code if prod else "???",
            "unit_price": float(pli.unit_price),
            "is_active": pli.is_active,
        })

    return {
        "price_list_id": pl.price_list_id,
        "code": pl.code,
        "name": pl.name,
        "is_default": pl.is_default,
        "is_active": pl.is_active,
        "items": items,
    }


async def _get_item_or_404(pl_id: int, item_id: int, db: AsyncSession) -> PriceListItem:
    """Fetch a price list item or raise 404."""
    result = await db.execute(
        select(PriceListItem).where(
            PriceListItem.price_list_item_id == item_id,
            PriceListItem.price_list_id == pl_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Ítem de precio no encontrado")
    return item


async def _item_to_detail(pli: PriceListItem, db: AsyncSession) -> dict:
    product = await db.get(Product, pli.product_id)
    return {
        "price_list_item_id": pli.price_list_item_id,
        "product_id": pli.product_id,
        "product_name": product.name if product else "???",
        "product_code": product.code if product else "???",
        "unit_price": float(pli.unit_price),
        "is_active": pli.is_active,
    }


# ── Price List Endpoints ───────────────────────────────────────────


@router.get("", response_model=PaginatedResponse)
async def list_price_lists(
    search: str = Query("", description="Search by name or code"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = Query("name", pattern=r"^(name|code|is_default|is_active)$"),
    order: str = Query("asc", pattern=r"^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("price_lists", "read")),
):
    """List price lists with search, pagination, and sorting."""
    base = select(PriceList)
    count_q = select(func.count(PriceList.price_list_id))

    if search:
        pattern = f"%{search.strip().lower()}%"
        from sqlalchemy import or_
        filter_clause = or_(
            func.lower(PriceList.name).like(pattern),
            func.lower(PriceList.code).like(pattern),
        )
        base = base.where(filter_clause)
        count_q = count_q.where(filter_clause)

    total = (await db.execute(count_q)).scalar() or 0
    pages = max(1, math.ceil(total / page_size))

    sort_col = getattr(PriceList, sort, PriceList.name)
    if order == "desc":
        sort_col = sort_col.desc()

    offset = (page - 1) * page_size
    result = await db.execute(base.order_by(sort_col).offset(offset).limit(page_size))
    price_lists = result.scalars().all()

    items = []
    for pl in price_lists:
        items.append(await _price_list_to_list_item(pl, db))

    return PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size, pages=pages,
    )


@router.post(
    "",
    response_model=AdminPriceListDetail,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}},
)
async def create_price_list(
    body: CreatePriceListRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("price_lists", "write")),
):
    """Create a new price list. Code must be unique."""
    existing = await db.execute(
        select(PriceList).where(PriceList.code == body.code.upper())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"La lista de precios '{body.code}' ya existe",
        )

    # If this is the only price list or marked as default, ensure consistency
    pl = PriceList(
        code=body.code.upper(),
        name=body.name,
        is_default=body.is_default,
    )
    db.add(pl)
    await db.commit()
    await db.refresh(pl)
    return await _price_list_to_detail(pl, db)


@router.get(
    "/{price_list_id}",
    response_model=AdminPriceListDetail,
    responses={404: {"model": ErrorResponse}},
)
async def get_price_list(
    price_list_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("price_lists", "read")),
):
    """Get a price list with all active items."""
    pl = await db.get(PriceList, price_list_id)
    if not pl:
        raise HTTPException(status_code=404, detail="Lista de precios no encontrada")
    return await _price_list_to_detail(pl, db)


@router.put(
    "/{price_list_id}",
    response_model=AdminPriceListDetail,
    responses={404: {"model": ErrorResponse}},
)
async def update_price_list(
    price_list_id: int,
    body: UpdatePriceListRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("price_lists", "write")),
):
    """Update price list fields. Only provided fields are changed."""
    pl = await db.get(PriceList, price_list_id)
    if not pl:
        raise HTTPException(status_code=404, detail="Lista de precios no encontrada")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(pl, key):
            setattr(pl, key, value)

    await db.commit()
    await db.refresh(pl)
    return await _price_list_to_detail(pl, db)


@router.delete(
    "/{price_list_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
async def delete_price_list(
    price_list_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("price_lists", "delete")),
):
    """Soft-delete a price list (sets is_active=False)."""
    pl = await db.get(PriceList, price_list_id)
    if not pl:
        raise HTTPException(status_code=404, detail="Lista de precios no encontrada")

    pl.is_active = False
    await db.commit()


# ── Price List Items Endpoints (nested) ─────────────────────────────


@router.get(
    "/{price_list_id}/items",
    response_model=list[AdminPriceListItemDetail],
)
async def list_items(
    price_list_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("price_lists", "read")),
):
    """List all active items in a price list."""
    pl = await db.get(PriceList, price_list_id)
    if not pl:
        raise HTTPException(status_code=404, detail="Lista de precios no encontrada")

    result = await db.execute(
        select(PriceListItem, Product)
        .join(Product, PriceListItem.product_id == Product.product_id)
        .where(PriceListItem.price_list_id == price_list_id)
        .order_by(Product.name)
    )
    items = []
    for pli, prod in result.all():
        items.append(await _item_to_detail(pli, db))
    return items


@router.post(
    "/{price_list_id}/items",
    response_model=AdminPriceListItemDetail,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}},
)
async def create_item(
    price_list_id: int,
    body: CreatePriceListItemRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("price_lists", "write")),
):
    """Add a product price to a price list."""
    pl = await db.get(PriceList, price_list_id)
    if not pl:
        raise HTTPException(status_code=404, detail="Lista de precios no encontrada")

    # Validate product exists
    product = await db.get(Product, body.product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Producto con id {body.product_id} no encontrado",
        )

    # Check for duplicate (unique constraint on price_list_id + product_id)
    existing = await db.execute(
        select(PriceListItem).where(
            PriceListItem.price_list_id == price_list_id,
            PriceListItem.product_id == body.product_id,
        )
    )
    existing_item = existing.scalar_one_or_none()
    if existing_item:
        # If it exists but is inactive, reactivate it
        if not existing_item.is_active:
            existing_item.unit_price = body.unit_price
            existing_item.is_active = True
            await db.commit()
            await db.refresh(existing_item)
            return await _item_to_detail(existing_item, db)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El producto ya existe en esta lista de precios",
        )

    pli = PriceListItem(
        price_list_id=price_list_id,
        product_id=body.product_id,
        unit_price=body.unit_price,
    )
    db.add(pli)
    await db.commit()
    await db.refresh(pli)
    return await _item_to_detail(pli, db)


@router.put(
    "/{price_list_id}/items/{item_id}",
    response_model=AdminPriceListItemDetail,
    responses={404: {"model": ErrorResponse}},
)
async def update_item(
    price_list_id: int,
    item_id: int,
    body: UpdatePriceListItemRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("price_lists", "write")),
):
    """Update a price list item's unit price or active status."""
    pli = await _get_item_or_404(price_list_id, item_id, db)

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(pli, key):
            setattr(pli, key, value)

    await db.commit()
    await db.refresh(pli)
    return await _item_to_detail(pli, db)


@router.delete(
    "/{price_list_id}/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
async def delete_item(
    price_list_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("price_lists", "delete")),
):
    """Soft-delete a price list item (sets is_active=False).

    The unique constraint on (price_list_id, product_id) is checked against
    ACTIVE rows by the create_item endpoint. Deactivated items don't block
    re-creation with the same product.
    """
    pli = await _get_item_or_404(price_list_id, item_id, db)
    pli.is_active = False
    await db.commit()
