"""Admin products CRUD — list, create, read, update, soft-delete.

Soft-delete is used for referential integrity (dispatch_details, price_list_items,
grades depend on products). Deleting sets is_active=False.
"""

import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.deps import get_admin_user, require_permission
from app.database import get_db
from app.models.product import Product, ProductCategory, TaxType
from app.models.user import User
from app.schemas import (
    AdminProductDetail,
    AdminProductListItem,
    CreateProductRequest,
    ErrorResponse,
    PaginatedResponse,
    UpdateProductRequest,
)

router = APIRouter(
    prefix="/api/admin/products",
    tags=["admin-products"],
    dependencies=[Depends(get_admin_user)],
)


# ── Helpers ────────────────────────────────────────────────────────


def _product_to_list_item(product: Product, category: ProductCategory) -> dict:
    return {
        "product_id": product.product_id,
        "code": product.code,
        "name": product.name,
        "category_id": product.category_id,
        "category_name": category.name if category else "???",
        "unit": product.unit,
        "base_price": float(product.base_price) if product.base_price else 0,
        "is_active": product.is_active,
    }


async def _product_to_detail(product: Product, db: AsyncSession) -> dict:
    """Build a detail dict with eagerly loaded or fetched relationships."""
    category = await db.get(ProductCategory, product.category_id)
    tax_type = await db.get(TaxType, product.tax_type_id) if product.tax_type_id else None

    return {
        "product_id": product.product_id,
        "code": product.code,
        "name": product.name,
        "category_id": product.category_id,
        "category_name": category.name if category else "???",
        "is_fuel": category.is_fuel if category else False,
        "unit": product.unit,
        "base_price": float(product.base_price) if product.base_price else 0,
        "subsidy_per_unit": float(product.subsidy_per_unit) if product.subsidy_per_unit else None,
        "tax_type_id": product.tax_type_id,
        "tax_type_name": tax_type.name if tax_type else None,
        "tax_rate": float(tax_type.rate) if tax_type else None,
        "is_active": product.is_active,
    }


# ── Endpoints ──────────────────────────────────────────────────────


@router.get("", response_model=PaginatedResponse)
async def list_products(
    search: str = Query("", description="Search by name or code"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = Query("name", pattern=r"^(name|code|category_id|unit|base_price|is_active)$"),
    order: str = Query("asc", pattern=r"^(asc|desc)$"),
    category: str = Query("", description="Filter by category code (e.g., FUEL)"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("products", "read")),
):
    """List products with search, pagination, sorting, and category filter."""
    # Base query with category joined
    base = select(Product, ProductCategory).join(
        ProductCategory, Product.category_id == ProductCategory.category_id, isouter=True
    )
    count_q = select(func.count(Product.product_id))

    # Filters
    if search:
        pattern = f"%{search.strip().lower()}%"
        from sqlalchemy import or_
        filter_clause = or_(
            func.lower(Product.name).like(pattern),
            func.lower(Product.code).like(pattern),
        )
        base = base.where(filter_clause)
        count_q = count_q.where(filter_clause)

    if category:
        base = base.where(ProductCategory.code == category.upper())
        count_q = count_q.join(
            ProductCategory, Product.category_id == ProductCategory.category_id
        ).where(ProductCategory.code == category.upper())

    # Count
    total = (await db.execute(count_q)).scalar() or 0
    pages = max(1, math.ceil(total / page_size))

    # Sort
    sort_col = getattr(Product, sort, Product.name)
    if order == "desc":
        sort_col = sort_col.desc()

    # Fetch page
    offset = (page - 1) * page_size
    result = await db.execute(base.order_by(sort_col).offset(offset).limit(page_size))
    rows = result.all()

    return PaginatedResponse(
        items=[_product_to_list_item(p, pc) for p, pc in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post(
    "",
    response_model=AdminProductDetail,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}},
)
async def create_product(
    body: CreateProductRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("products", "write")),
):
    """Create a new product. Code must be unique."""
    # Check code uniqueness
    existing = await db.execute(
        select(Product).where(Product.code == body.code.upper())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El producto con código '{body.code}' ya existe",
        )

    # Validate category exists
    category = await db.get(ProductCategory, body.category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Categoría con id {body.category_id} no encontrada",
        )

    # Validate tax type if provided
    if body.tax_type_id is not None:
        tax_type = await db.get(TaxType, body.tax_type_id)
        if not tax_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo de impuesto con id {body.tax_type_id} no encontrado",
            )

    product = Product(
        code=body.code.upper(),
        name=body.name,
        category_id=body.category_id,
        unit=body.unit,
        base_price=body.base_price,
        subsidy_per_unit=body.subsidy_per_unit,
        tax_type_id=body.tax_type_id,
        is_active=body.is_active,
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return await _product_to_detail(product, db)


@router.get(
    "/{product_id}",
    response_model=AdminProductDetail,
    responses={404: {"model": ErrorResponse}},
)
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("products", "read")),
):
    """Get a single product by id, including category and tax info."""
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return await _product_to_detail(product, db)


@router.put(
    "/{product_id}",
    response_model=AdminProductDetail,
    responses={404: {"model": ErrorResponse}},
)
async def update_product(
    product_id: int,
    body: UpdateProductRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("products", "write")),
):
    """Update product fields. Only provided fields are changed.

    The product code cannot be changed (stable identifier).
    Use is_active=False to deactivate.
    Sending a field as null explicitly clears it (e.g., subsidy_per_unit=None).
    """
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    # model_dump(exclude_unset=True) only includes fields the client sent.
    # This lets us distinguish "field absent" from "field sent as null".
    update_data = body.model_dump(exclude_unset=True)

    # Validate FK references before applying
    if "category_id" in update_data:
        category = await db.get(ProductCategory, update_data["category_id"])
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Categoría con id {update_data['category_id']} no encontrada",
            )
    if "tax_type_id" in update_data:
        tax_type = await db.get(TaxType, update_data["tax_type_id"])
        if not tax_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo de impuesto con id {update_data['tax_type_id']} no encontrado",
            )

    # Apply all provided fields (including explicit nulls)
    for key, value in update_data.items():
        if hasattr(product, key):
            setattr(product, key, value)

    await db.commit()
    await db.refresh(product)
    return await _product_to_detail(product, db)


@router.get("/categories", response_model=list)
async def list_categories(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("products", "read")),
):
    """List all product categories (for dropdowns)."""
    result = await db.execute(select(ProductCategory).order_by(ProductCategory.name))
    return [{"category_id": c.category_id, "code": c.code, "name": c.name, "is_fuel": c.is_fuel} for c in result.scalars().all()]


@router.get("/tax-types", response_model=list)
async def list_tax_types(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("products", "read")),
):
    """List all tax types (for dropdowns)."""
    result = await db.execute(select(TaxType).order_by(TaxType.name))
    return [{"tax_type_id": t.tax_type_id, "code": t.code, "name": t.name, "rate": float(t.rate)} for t in result.scalars().all()]


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("products", "delete")),
):
    """Soft-delete a product (sets is_active=False).

    Referential integrity: dispatch_details, price_list_items, and grades
    may reference this product. Soft-delete preserves those references.
    """
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    product.is_active = False
    await db.commit()
