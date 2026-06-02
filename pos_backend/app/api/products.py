"""Product catalog and reference data endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models import (
    DispatchType,
    PriceList,
    Product,
    ProductCategory,
)
from app.models.user import User
from app.schemas import (
    DispatchTypeResponse,
    PriceListResponse,
    ProductCategoryResponse,
    ProductResponse,
)

router = APIRouter(prefix="/api/pos", tags=["products"])


@router.get("/products", response_model=list[ProductResponse])
async def list_products(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """List all active products with their categories."""
    result = await db.execute(
        select(Product, ProductCategory)
        .join(ProductCategory, Product.category_id == ProductCategory.category_id)
        .where(Product.is_active == True)
        .order_by(ProductCategory.name, Product.name)
    )
    rows = result.all()

    return [
        ProductResponse(
            product_id=p.product_id,
            code=p.code,
            name=p.name,
            category_id=p.category_id,
            category_name=pc.name,
            unit=p.unit,
            base_price=p.base_price,
            is_fuel=pc.is_fuel,
            is_active=p.is_active,
        )
        for p, pc in rows
    ]


@router.get("/product-categories", response_model=list[ProductCategoryResponse])
async def list_categories(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """List all product categories."""
    result = await db.execute(select(ProductCategory).order_by(ProductCategory.name))
    categories = result.scalars().all()
    return [
        ProductCategoryResponse(
            category_id=c.category_id,
            code=c.code,
            name=c.name,
            is_fuel=c.is_fuel,
        )
        for c in categories
    ]


@router.get("/price-lists", response_model=list[PriceListResponse])
async def list_price_lists(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """List all price lists."""
    result = await db.execute(select(PriceList).order_by(PriceList.name))
    pls = result.scalars().all()
    return [PriceListResponse(code=pl.code, name=pl.name) for pl in pls]


@router.get("/dispatch-types", response_model=list[DispatchTypeResponse])
async def list_dispatch_types(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """List all dispatch types."""
    result = await db.execute(select(DispatchType).order_by(DispatchType.name))
    types = result.scalars().all()
    return [
        DispatchTypeResponse(
            dispatch_type_id=dt.dispatch_type_id,
            code=dt.code,
            name=dt.name,
            requires_customer=dt.requires_customer,
            affects_cash=dt.affects_cash,
        )
        for dt in types
    ]
