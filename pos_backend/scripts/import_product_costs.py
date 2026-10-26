"""Import effective-dated purchase costs from a CSV file.

Expected columns (case-insensitive, Spanish or English headers)::

    product_code,valid_from,cost_price,notes
    INV000007,2026-09-01,2.5870,Costo factura 001-001-000123
    INV000002,2026-09-01,4.5269,
    INV000026,2026-09-01,2.6309,

Accepted aliases:
    product_code : product_code, code, codigo, codigo_producto
    valid_from   : valid_from, fecha_desde, desde
    cost_price   : cost_price, costo, costo_neto, precio_compra
    notes        : notes, notas, observacion

All costs are NET of VAT. The script is a DRY-RUN by default.

Usage::

    cd pos_backend && source venv/bin/activate
    python scripts/import_product_costs.py --file costos.csv
    python scripts/import_product_costs.py --file costos.csv --apply
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import select

from app.database import async_session
from app.models.product import Product
from app.services.cost_service import upsert_cost

ALIASES = {
    "product_code": {"product_code", "code", "codigo", "código", "codigo_producto"},
    "valid_from": {"valid_from", "fecha_desde", "desde", "vigente_desde"},
    "cost_price": {"cost_price", "costo", "costo_neto", "precio_compra", "costo_sin_iva"},
    "notes": {"notes", "notas", "observacion", "observación"},
}


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--file", required=True, help="Path to the CSV file")
    p.add_argument("--apply", action="store_true", help="Write the rows (default: dry-run)")
    p.add_argument("--source", default="ERP", choices=["ERP", "MANUAL", "EXAMPLE"])
    p.add_argument("--force", action="store_true", help="Overwrite rows from another source")
    return p.parse_args(argv)


def _norm(value: str) -> str:
    return (value or "").strip().lower()


def _column_map(fieldnames: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for raw in fieldnames:
        key = _norm(raw)
        for canonical, names in ALIASES.items():
            if key in names:
                mapping[canonical] = raw
                break
    missing = {"product_code", "valid_from", "cost_price"} - set(mapping)
    if missing:
        raise ValueError(f"Faltan columnas en el CSV: {', '.join(sorted(missing))}")
    return mapping


def _parse_date(value: str) -> date:
    value = (value or "").strip()
    # Accept ISO (2026-09-01) and Ecuadorian (01/09/2026).
    if "/" in value:
        d, m, y = value.split("/")
        return date(int(y), int(m), int(d))
    return date.fromisoformat(value)


async def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    path = Path(args.file)
    if not path.exists():
        print(f"No existe el archivo: {path}")
        return 1

    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            print("El CSV está vacío o no tiene encabezados.")
            return 1
        cols = _column_map(reader.fieldnames)
        rows = list(reader)

    async with async_session() as session:
        products = (await session.execute(select(Product.product_id, Product.code))).all()
        by_code = {_norm(code): pid for pid, code in products}
        # Also accept numeric product_id in the product_code column.
        by_id = {str(pid): pid for pid, _ in products}

        ok = 0
        errors = 0
        for line_no, row in enumerate(rows, start=2):
            raw_code = (row.get(cols["product_code"]) or "").strip()
            pid = by_code.get(_norm(raw_code)) or by_id.get(raw_code)
            if not pid:
                print(f"  línea {line_no}: producto '{raw_code}' no encontrado")
                errors += 1
                continue
            try:
                valid_from = _parse_date(row.get(cols["valid_from"], ""))
                cost = float((row.get(cols["cost_price"]) or "").replace(",", "."))
            except Exception as exc:
                print(f"  línea {line_no}: dato inválido ({exc})")
                errors += 1
                continue

            notes = (row.get(cols["notes"]) or "").strip() if "notes" in cols else None
            if not args.apply:
                print(f"  [dry-run] línea {line_no}: product_id={pid} desde={valid_from} costo=${cost:.4f}")
                ok += 1
                continue
            try:
                await upsert_cost(
                    session,
                    product_id=pid,
                    valid_from=valid_from,
                    cost_price=cost,
                    source=args.source,
                    notes=notes or None,
                    force=args.force,
                )
                ok += 1
            except ValueError as exc:
                print(f"  línea {line_no}: {exc}")
                errors += 1

        mode = "escritas" if args.apply else "[dry-run] válidas"
        print(f"\nFilas {mode}: {ok} · errores: {errors}")
        if args.apply and ok:
            print("Ejecuta scripts/backfill_dispatch_costs.py para congelar el costo histórico.")
    return 0 if errors == 0 else 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
