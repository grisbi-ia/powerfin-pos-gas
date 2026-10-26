"""Freeze the effective purchase cost into historical dispatch details.

For every ``dispatch_details`` row without ``unit_cost``, look up the cost that
was effective on the dispatch date and write it. Details whose date has no
cost row stay NULL on purpose: the dashboard marks those buckets as
incomplete instead of assuming a zero cost.

DRY-RUN by default.

Usage::

    cd pos_backend && source venv/bin/activate
    python scripts/backfill_dispatch_costs.py
    python scripts/backfill_dispatch_costs.py --apply
    python scripts/backfill_dispatch_costs.py --since 2026-09-01 --apply

Production (read/write via Tailscale)::

    DATABASE_HOST=100.97.47.123 DATABASE_PORT=5432 DATABASE_NAME=powerfin_gas \\
    DATABASE_USER=agent_llm DATABASE_PASSWORD=... PYTHONPATH=. \\
    python scripts/backfill_dispatch_costs.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date

from sqlalchemy import text

from app.database import async_session

COUNT_SQL = """
SELECT COUNT(*)
FROM dispatch_details dd
JOIN dispatches d ON d.dispatch_id = dd.dispatch_id
WHERE dd.unit_cost IS NULL
  {since_filter}
  AND EXISTS (
      SELECT 1
      FROM product_cost_history pc
      WHERE pc.product_id = dd.product_id
        AND pc.valid_from <= (d.created_at AT TIME ZONE 'America/Guayaquil')::date
  )
"""

SAMPLE_SQL = """
SELECT dd.detail_id, dd.product_id, d.order_id,
       (d.created_at AT TIME ZONE 'America/Guayaquil')::date AS sale_date
FROM dispatch_details dd
JOIN dispatches d ON d.dispatch_id = dd.dispatch_id
WHERE dd.unit_cost IS NULL
  {since_filter}
  AND EXISTS (
      SELECT 1
      FROM product_cost_history pc
      WHERE pc.product_id = dd.product_id
        AND pc.valid_from <= (d.created_at AT TIME ZONE 'America/Guayaquil')::date
  )
ORDER BY d.created_at
LIMIT 20
"""

UPDATE_SQL = """
UPDATE dispatch_details dd
SET unit_cost = (
    SELECT pc.cost_price
    FROM product_cost_history pc
    WHERE pc.product_id = dd.product_id
      AND pc.valid_from <= (d.created_at AT TIME ZONE 'America/Guayaquil')::date
    ORDER BY pc.valid_from DESC
    LIMIT 1
)
FROM dispatches d
WHERE dd.dispatch_id = d.dispatch_id
  AND dd.unit_cost IS NULL
  {since_filter}
  AND EXISTS (
      SELECT 1
      FROM product_cost_history pc
      WHERE pc.product_id = dd.product_id
        AND pc.valid_from <= (d.created_at AT TIME ZONE 'America/Guayaquil')::date
  )
"""

REMAINING_SQL = """
SELECT COUNT(*)
FROM dispatch_details
WHERE unit_cost IS NULL
"""


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--apply", action="store_true", help="Write the values (default: dry-run)")
    p.add_argument("--since", type=date.fromisoformat, default=None, help="Only rows on/after this date (YYYY-MM-DD)")
    return p.parse_args(argv)


async def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    since_filter = ""
    params: dict = {}
    if args.since:
        since_filter = "AND (d.created_at AT TIME ZONE 'America/Guayaquil')::date >= :since"
        params["since"] = args.since

    count_sql = COUNT_SQL.format(since_filter=since_filter)
    sample_sql = SAMPLE_SQL.format(since_filter=since_filter)
    update_sql = UPDATE_SQL.format(since_filter=since_filter)

    async with async_session() as session:
        pending = (await session.execute(text(count_sql), params)).scalar() or 0
        print(f"Detalles sin costo con una vigencia disponible: {pending}")
        if pending == 0:
            print("Nada que hacer.")
            return 0

        sample = (await session.execute(text(sample_sql), params)).all()
        print("\nPrimeros registros que se actualizarían:")
        for detail_id, product_id, order_id, sale_date in sample:
            print(f"  detail={detail_id} product={product_id} order={order_id} fecha={sale_date}")

        if not args.apply:
            print("\n[dry-run] Usa --apply para escribir.")
            return 0

        result = await session.execute(text(update_sql), params)
        await session.commit()
        print(f"\nFilas actualizadas: {result.rowcount}")

        remaining = (await session.execute(text(REMAINING_SQL))).scalar() or 0
        print(f"Detalles que siguen sin costo (sin vigencia para su fecha): {remaining}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
