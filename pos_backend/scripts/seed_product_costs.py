"""Seed EXAMPLE purchase costs for the fuel products.

These values are placeholders until the real cost history arrives from the
ERP. They are marked with ``source='EXAMPLE'`` so the Admin UI (and the
dashboard warning) can tell them apart from real data.

Usage::

    cd pos_backend && source venv/bin/activate
    python scripts/seed_product_costs.py            # dry-run
    python scripts/seed_product_costs.py --apply    # write EXAMPLE rows

The script is idempotent: running it again updates the EXAMPLE rows for the
same (product, valid_from) and never overwrites MANUAL/ERP rows.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date

from sqlalchemy import select

from app.database import async_session
from app.models.product import Product
from app.services.cost_service import upsert_cost

# Example costs NET of VAT, derived from plausible Ecuadorian fuel margins.
# NOT REAL DATA — replace with the ERP purchase invoices.
EXAMPLE_COSTS: dict[str, list[tuple[date, float]]] = {
    "diesel": [
        (date(2026, 6, 1), 2.5500),
        (date(2026, 7, 1), 2.5650),
        (date(2026, 8, 1), 2.5750),
        (date(2026, 9, 1), 2.5870),
        (date(2026, 9, 15), 2.5970),
        (date(2026, 10, 1), 2.6070),
        (date(2026, 10, 15), 2.6120),
        (date(2026, 10, 22), 2.6170),
    ],
    "super": [
        (date(2026, 6, 1), 4.4900),
        (date(2026, 7, 1), 4.5050),
        (date(2026, 8, 1), 4.5150),
        (date(2026, 9, 1), 4.5269),
        (date(2026, 9, 15), 4.5369),
        (date(2026, 10, 1), 4.5469),
        (date(2026, 10, 15), 4.5519),
        (date(2026, 10, 22), 4.5569),
    ],
    "eco": [
        (date(2026, 6, 1), 2.6000),
        (date(2026, 7, 1), 2.6150),
        (date(2026, 8, 1), 2.6250),
        (date(2026, 9, 1), 2.6309),
        (date(2026, 9, 15), 2.6409),
        (date(2026, 10, 1), 2.6509),
        (date(2026, 10, 15), 2.6559),
        (date(2026, 10, 22), 2.6609),
    ],
}

NAME_HINTS = {
    "diesel": ("diesel", "diesel 2"),
    "super": ("super", "gasolina super", "súper"),
    "eco": ("eco", "eco país", "eco pais", "ecopais"),
}

NOTE = "Dato de ejemplo — reemplazar con el costo de compra del ERP"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--apply", action="store_true", help="Write the rows (default: dry-run)")
    p.add_argument("--reset", action="store_true", help="Delete existing EXAMPLE rows before seeding")
    return p.parse_args(argv)


async def _resolve_products(session) -> dict[str, int]:
    rows = (await session.execute(select(Product.product_id, Product.name))).all()
    catalog = [(pid, (name or "").strip().lower()) for pid, name in rows]
    resolved: dict[str, int] = {}
    for key, hints in NAME_HINTS.items():
        for pid, name in catalog:
            if any(hint in name for hint in hints):
                resolved[key] = pid
                break
    return resolved


async def main(argv: list[str]) -> int:
    args = _parse_args(argv)

    async with async_session() as session:
        products = await _resolve_products(session)
        if not products:
            print("No se encontraron productos de combustible (Diesel / Super / Eco País).")
            return 1

        print("Productos resueltos:")
        for key, pid in products.items():
            print(f"  {key:6s} -> product_id={pid}")

        if args.reset and args.apply:
            from app.models.product_cost import ProductCost
            deleted = await session.execute(
                ProductCost.__table__.delete().where(ProductCost.source == "EXAMPLE")
            )
            await session.commit()
            print(f"Filas EXAMPLE eliminadas: {deleted.rowcount}")

        total = 0
        skipped = 0
        for key, rows in EXAMPLE_COSTS.items():
            pid = products.get(key)
            if not pid:
                print(f"  ! {key}: producto no encontrado, se omite")
                continue
            for valid_from, cost in rows:
                if not args.apply:
                    print(f"  [dry-run] {key:6s} {valid_from.isoformat()} ${cost:.4f}")
                    total += 1
                    continue
                try:
                    await upsert_cost(
                        session,
                        product_id=pid,
                        valid_from=valid_from,
                        cost_price=cost,
                        source="EXAMPLE",
                        notes=NOTE,
                        force=False,
                    )
                    total += 1
                except ValueError as exc:
                    print(f"  ! {key} {valid_from}: {exc}")
                    skipped += 1

        if args.apply:
            print(f"\nFilas EXAMPLE escritas/actualizadas: {total} · omitidas: {skipped}")
            print("Recuerda ejecutar scripts/backfill_dispatch_costs.py para congelar")
            print("el costo en los despachos históricos.")
        else:
            print(f"\n[dry-run] {total} filas. Usa --apply para escribir.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
