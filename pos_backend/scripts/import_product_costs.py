"""Import effective-dated purchase costs from a CSV file.

Expected columns (case-insensitive, Spanish or English headers)::

    product_code,valid_from,cost_price,notes
    INV000007,2026-09-01,2.5870,Costo factura 001-001-000123
    INV000002,2026-09-01,4.5269,
    INV000026,2026-09-01,2.6309,

Accepted aliases:
    product_code : product_code, product_id, code, codigo, codigo_producto
    valid_from   : valid_from, fecha_desde, desde, vigente_desde
    cost_price   : cost_price, costo, costo_neto, precio_compra, costo_sin_iva
    notes        : notes, notas, observacion

`product_code` may also be a numeric product_id (e.g. 1, 2, 3).

All costs are NET of VAT. The script is a DRY-RUN by default.

If the same (product, valid_from) appears more than once, `--on-duplicate`
decides what to do (default: `average`):

    average  simple average of the duplicate values (default; two purchases
             on the same day without volume data)
    last     keep the last row in file order
    first    keep the first row in file order
    error    abort without writing anything

Usage::

    cd pos_backend && source venv/bin/activate
    python scripts/import_product_costs.py --file costos.csv
    python scripts/import_product_costs.py --file costos.csv --apply
    python scripts/import_product_costs.py --file costos.csv --apply --on-duplicate average
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

from sqlalchemy import select

from app.database import async_session
from app.models.product import Product
from app.services.cost_service import upsert_cost

ALIASES = {
    "product_code": {
        "product_code", "product_id", "code", "codigo", "código", "codigo_producto"
    },
    "valid_from": {"valid_from", "fecha_desde", "desde", "vigente_desde"},
    "cost_price": {"cost_price", "costo", "costo_neto", "precio_compra", "costo_sin_iva"},
    "notes": {"notes", "notas", "observacion", "observación"},
}

DUPLICATE_POLICIES = ("last", "first", "average", "error")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--file", required=True, help="Path to the CSV file")
    p.add_argument("--apply", action="store_true", help="Write the rows (default: dry-run)")
    p.add_argument("--source", default="ERP", choices=["ERP", "MANUAL", "EXAMPLE"])
    p.add_argument("--force", action="store_true", help="Overwrite rows from another source")
    p.add_argument(
        "--on-duplicate",
        default="average",
        choices=DUPLICATE_POLICIES,
        help="What to do when (product, valid_from) repeats (default: average)",
    )
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


def _pick_value(entries: list[dict], policy: str) -> float:
    values = [e["cost"] for e in entries]
    if policy == "first":
        return values[0]
    if policy == "average":
        return sum(values) / len(values)
    # last (default)
    return values[-1]


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
        raw_rows = list(reader)

    async with async_session() as session:
        products = (await session.execute(select(Product.product_id, Product.code))).all()
        by_code = {_norm(code): pid for pid, code in products}
        by_id = {str(pid): pid for pid, _ in products}

        parsed: list[dict] = []
        errors = 0
        for line_no, row in enumerate(raw_rows, start=2):
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
            if cost < 0:
                print(f"  línea {line_no}: costo negativo ({cost})")
                errors += 1
                continue
            notes = (row.get(cols["notes"]) or "").strip() if "notes" in cols else None
            parsed.append({
                "line_no": line_no,
                "pid": pid,
                "valid_from": valid_from,
                "cost": cost,
                "notes": notes or None,
            })

        # Group duplicates by (product_id, valid_from)
        groups: dict[tuple[int, date], list[dict]] = defaultdict(list)
        for item in parsed:
            groups[(item["pid"], item["valid_from"])].append(item)

        duplicates = {k: v for k, v in groups.items() if len(v) > 1}
        if duplicates:
            print(f"\nDuplicados encontrados: {len(duplicates)} fechas")
            for (pid, valid_from), entries in sorted(
                duplicates.items(), key=lambda kv: (kv[0][0], kv[0][1])
            ):
                values = ", ".join(f"{e['cost']:.8f} (línea {e['line_no']})" for e in entries)
                if args.on_duplicate == "error":
                    print(f"  product_id={pid} {valid_from}: {values} → conflicto")
                else:
                    chosen = _pick_value(entries, args.on_duplicate)
                    print(f"  product_id={pid} {valid_from}: {values} → se usa {chosen:.8f}")

        if duplicates and args.on_duplicate == "error":
            print("\n[error] Hay duplicados y --on-duplicate=error: no se escribió nada.")
            return 2

        # One row per (product, valid_from), sorted for a readable dry-run
        unique_rows = []
        for (pid, valid_from), entries in sorted(
            groups.items(), key=lambda kv: (kv[0][0], kv[0][1])
        ):
            unique_rows.append({
                "pid": pid,
                "valid_from": valid_from,
                "cost": _pick_value(entries, args.on_duplicate),
                "notes": entries[-1]["notes"],
            })

        if not args.apply:
            print(f"\n[dry-run] {len(unique_rows)} vigencias únicas:")
            for item in unique_rows:
                print(
                    f"  product_id={item['pid']}  {item['valid_from']}  "
                    f"${item['cost']:.4f}"
                )
            print(
                f"\nFilas leídas: {len(raw_rows)} · vigencias únicas: {len(unique_rows)} · "
                f"duplicados: {len(duplicates)} · errores: {errors}"
            )
            print("Usa --apply para escribir.")
            return 0 if errors == 0 else 2

        written = 0
        for item in unique_rows:
            try:
                await upsert_cost(
                    session,
                    product_id=item["pid"],
                    valid_from=item["valid_from"],
                    cost_price=item["cost"],
                    source=args.source,
                    notes=item["notes"],
                    force=args.force,
                )
                written += 1
            except ValueError as exc:
                print(f"  product_id={item['pid']} {item['valid_from']}: {exc}")
                errors += 1

        print(
            f"\nVigencias escritas: {written} · duplicados resueltos: {len(duplicates)} · "
            f"errores: {errors}"
        )
        if written:
            print("Ejecuta scripts/backfill_dispatch_costs.py para congelar el costo histórico.")
    return 0 if errors == 0 else 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
