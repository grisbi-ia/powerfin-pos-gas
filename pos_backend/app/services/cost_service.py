"""Effective-dated purchase costs per product.

The table stores only ``valid_from``. The end of a period is the day before
the next row's ``valid_from``; the last row is open-ended. This keeps the
history free of gaps and overlaps without extra maintenance.

All monetary values are NET of VAT.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.product_cost import ProductCost

ALLOWED_SOURCES = {"MANUAL", "ERP", "EXAMPLE"}


async def get_cost_at(
    db: AsyncSession, product_id: int, on_date: date
) -> Decimal | None:
    """Return the cost effective on ``on_date``, or None if not configured."""
    result = await db.execute(
        select(ProductCost.cost_price)
        .where(
            ProductCost.product_id == product_id,
            ProductCost.valid_from <= on_date,
        )
        .order_by(ProductCost.valid_from.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_current_costs(
    db: AsyncSession, product_ids: list[int], on_date: date | None = None
) -> dict[int, Decimal]:
    """Bulk lookup of the current cost for several products (one query)."""
    if not product_ids:
        return {}
    on_date = on_date or date.today()
    result = await db.execute(
        select(ProductCost.product_id, ProductCost.cost_price)
        .where(
            ProductCost.product_id.in_(product_ids),
            ProductCost.valid_from <= on_date,
        )
        .order_by(ProductCost.product_id, ProductCost.valid_from.desc())
        .distinct(ProductCost.product_id)
    )
    return {pid: cost for pid, cost in result.all()}


async def list_cost_history(db: AsyncSession, product_id: int) -> list[dict]:
    """Return the full history with a computed ``valid_to`` and ``is_current``."""
    result = await db.execute(
        select(ProductCost)
        .where(ProductCost.product_id == product_id)
        .order_by(ProductCost.valid_from.asc())
    )
    rows = result.scalars().all()
    today = date.today()

    items: list[dict] = []
    current_id: int | None = None
    for idx, row in enumerate(rows):
        valid_to = (
            rows[idx + 1].valid_from - timedelta(days=1)
            if idx + 1 < len(rows)
            else None
        )
        if row.valid_from <= today and (valid_to is None or valid_to >= today):
            current_id = row.product_cost_id
    for idx, row in enumerate(rows):
        valid_to = (
            rows[idx + 1].valid_from - timedelta(days=1)
            if idx + 1 < len(rows)
            else None
        )
        items.append(
            {
                "product_cost_id": row.product_cost_id,
                "product_id": row.product_id,
                "valid_from": row.valid_from,
                "valid_to": valid_to,
                "cost_price": float(row.cost_price),
                "source": row.source,
                "notes": row.notes,
                "is_current": row.product_cost_id == current_id,
            }
        )
    return items


async def upsert_cost(
    db: AsyncSession,
    product_id: int,
    valid_from: date,
    cost_price: float,
    source: str = "MANUAL",
    notes: str | None = None,
    created_by: int | None = None,
    force: bool = False,
) -> ProductCost:
    """Insert a cost row, or update it if (product, valid_from) already exists.

    A row coming from ERP/EXAMPLE is not overwritten by a MANUAL row unless
    ``force`` is true; this avoids silently replacing real data with a seed.
    """
    if source not in ALLOWED_SOURCES:
        raise ValueError(f"Fuente de costo inválida: {source}")
    if cost_price < 0:
        raise ValueError("El costo no puede ser negativo")

    product = await db.get(Product, product_id)
    if not product:
        raise ValueError("Producto no encontrado")

    existing = (
        await db.execute(
            select(ProductCost).where(
                ProductCost.product_id == product_id,
                ProductCost.valid_from == valid_from,
            )
        )
    ).scalar_one_or_none()

    if existing:
        if existing.source != source and not force:
            raise ValueError(
                f"Ya existe un costo para esa fecha con origen {existing.source}. "
                "Usa force para reemplazarlo."
            )
        existing.cost_price = cost_price
        existing.source = source
        if notes is not None:
            existing.notes = notes
        await db.commit()
        await db.refresh(existing)
        return existing

    row = ProductCost(
        product_id=product_id,
        valid_from=valid_from,
        cost_price=cost_price,
        source=source,
        notes=notes,
        created_by=created_by,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def update_cost(
    db: AsyncSession,
    product_id: int,
    cost_id: int,
    valid_from: date | None = None,
    cost_price: float | None = None,
    notes: str | None = None,
) -> ProductCost | None:
    row = (
        await db.execute(
            select(ProductCost).where(
                ProductCost.product_cost_id == cost_id,
                ProductCost.product_id == product_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        return None

    if valid_from is not None and valid_from != row.valid_from:
        clash = (
            await db.execute(
                select(ProductCost).where(
                    ProductCost.product_id == product_id,
                    ProductCost.valid_from == valid_from,
                    ProductCost.product_cost_id != cost_id,
                )
            )
        ).scalar_one_or_none()
        if clash:
            raise ValueError("Ya existe otro costo con esa fecha desde")
        row.valid_from = valid_from
    if cost_price is not None:
        if cost_price < 0:
            raise ValueError("El costo no puede ser negativo")
        row.cost_price = cost_price
    if notes is not None:
        row.notes = notes

    await db.commit()
    await db.refresh(row)
    return row


async def delete_cost(db: AsyncSession, product_id: int, cost_id: int) -> bool:
    row = (
        await db.execute(
            select(ProductCost).where(
                ProductCost.product_cost_id == cost_id,
                ProductCost.product_id == product_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        return False
    await db.delete(row)
    await db.commit()
    return True
