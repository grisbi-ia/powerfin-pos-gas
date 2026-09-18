#!/usr/bin/env python3
"""Mark dispatches as invoiced when the invoice was issued in Powerfin ERP.

Why: public-sector contracts (NO_INDEFINIDO) collect dispatches as
PENDING_BULK_INVOICE to be invoiced later in a single global SRI invoice. When
that invoice is issued **directly from the ERP** instead of the POS Backend,
the local dispatches stay PENDING_BULK_INVOICE with sri_status PENDING/FAILED:
they keep showing as "pending to invoice" and as SRI problems.

This reconciles those rows to their real state:
  * credit_status           -> INVOICED   (the state bulk-invoice sets on success)
  * sri_status              -> AUTHORIZED (FINAL_OK for the SRI monitor/reports)
  * sri_authorization_date  -> the ERP authorization date
  * sri_messages            -> NULL       (clears the old error)
  * with --clear-sequential: sequential_number and access_key -> NULL, for rows
    that were first attempted as individual invoices but ended up in the ERP
    batch (they never reached Key49, so there is no document to keep).

Selection: `--contract-id` (+ `--source-status`) or `--dispatch-id` (repeatable).

Safety
------
* Dry-run by default; `--apply` writes.
* Before writing, dumps every affected row to a CSV backup under
  `~/.powerfin_backups/` (persistent, NOT /tmp).
* Idempotent: only rows matching the filter are selected.
* Never touches CANCELLED dispatches.

Usage
-----
    cd pos_backend && source venv/bin/activate
    python ../scripts/marcar_facturado_erp.py --contract-id 3 \
        --auth-date 2026-08-24                 # dry-run (prod batch)
    python ../scripts/marcar_facturado_erp.py --dispatch-id 7249 \
        --dispatch-id 9288 --auth-date 2026-08-24 --clear-sequential --apply

Environment: DSN defaults to the production read/write user from docs/DB_ACCESS.md.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import os
from datetime import datetime, timedelta, timezone

DEFAULT_DSN = "postgresql://agent_llm:AgentLLM123@100.97.47.123:5432/powerfin_gas"
DEFAULT_BACKUP_DIR = os.path.expanduser("~/.powerfin_backups")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--contract-id", type=int, help="credit_contracts.contract_id")
    p.add_argument("--dispatch-id", type=int, action="append",
                   help="Specific dispatch id (repeatable; overrides --contract-id)")
    p.add_argument("--auth-date", required=True, help="SRI authorization date (YYYY-MM-DD)")
    p.add_argument("--source-status", default="PENDING_BULK_INVOICE",
                   help="credit_status to convert in contract mode (default PENDING_BULK_INVOICE)")
    p.add_argument("--clear-sequential", action="store_true",
                   help="Also set sequential_number and access_key to NULL")
    p.add_argument("--apply", action="store_true", help="Actually write (default: dry-run)")
    p.add_argument("--dsn", default=DEFAULT_DSN)
    p.add_argument("--backup-dir", default=DEFAULT_BACKUP_DIR)
    args = p.parse_args()
    if not args.dispatch_id and args.contract_id is None:
        p.error("se requiere --contract-id o al menos un --dispatch-id")
    return args


def _where_and_params(args) -> tuple[str, list]:
    conds = ["status <> 'CANCELLED'"]
    params: list = []
    if args.dispatch_id:
        params.append(list(args.dispatch_id))
        conds.append(f"dispatch_id = ANY(${len(params)}::int[])")
    else:
        params.append(args.contract_id)
        conds.append(f"credit_contract_id = ${len(params)}")
        params.append(args.source_status)
        conds.append(f"credit_status = ${len(params)}")
    return " AND ".join(conds), params


async def main() -> int:
    args = _parse_args()
    try:
        datetime.strptime(args.auth_date, "%Y-%m-%d")
    except ValueError:
        print(f"ERROR: --auth-date debe ser YYYY-MM-DD (recibido: {args.auth_date})")
        return 2

    import asyncpg

    where, params = _where_and_params(args)
    select_sql = (
        "SELECT dispatch_id, order_id, created_at, total, status, credit_status, "
        "sri_status, sri_messages, person_id, credit_contract_id, "
        "sequential_number, access_key, key49_invoice_id "
        f"FROM dispatches WHERE {where} ORDER BY dispatch_id"
    )

    conn = await asyncpg.connect(args.dsn)
    try:
        rows = await conn.fetch(select_sql, *params)

        scope = (f"dispatch_ids={args.dispatch_id}" if args.dispatch_id
                 else f"contract_id={args.contract_id} source_status={args.source_status}")
        print(f"=== Marcar facturado en ERP — {'APPLY' if args.apply else 'DRY-RUN'} ===")
        print(f"{scope} auth_date={args.auth_date} clear_sequential={args.clear_sequential}")

        total = sum(float(r["total"] or 0) for r in rows)
        print(f"\nFilas afectadas: {len(rows)} · monto ${total:,.2f}")

        by_status: dict[str, int] = {}
        for r in rows:
            key = r["sri_status"] or "NULL"
            by_status[key] = by_status.get(key, 0) + 1
        if by_status:
            print("  sri_status actual:", by_status)

        if not rows:
            print("\nNada que hacer.")
            return 0

        # Guard: never clear a sequential that Key49 actually used.
        used = [r["dispatch_id"] for r in rows if r["key49_invoice_id"]]
        if used and args.clear_sequential:
            print(f"\nABORT: {len(used)} fila(s) tienen key49_invoice_id; "
                  f"no se limpia el secuencial: {used}")
            return 2

        print("\nPrimeras 5 filas:")
        for r in rows[:5]:
            extra = f" · seq={r['sequential_number']}" if args.clear_sequential else ""
            print(f"  #{r['dispatch_id']} {r['order_id']} · {r['created_at']:%Y-%m-%d} · "
                  f"${float(r['total'] or 0):,.2f} · sri={r['sri_status']}{extra}")

        if not args.apply:
            print("\nDRY-RUN: no se escribió nada. Repetir con --apply.")
            return 0

        # 1) Backup to CSV (persistent, outside /tmp).
        os.makedirs(args.backup_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        tag = (f"dispatches{len(args.dispatch_id)}" if args.dispatch_id
               else f"contract{args.contract_id}")
        backup_path = os.path.join(args.backup_dir, f"facturado_erp_{tag}_{stamp}.csv")
        with open(backup_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(rows[0].keys())
            for r in rows:
                writer.writerow(list(r.values()))
        print(f"\nRespaldo: {backup_path} ({len(rows)} filas)")

        # 2) Apply (idempotent via the WHERE clause).
        auth_dt = datetime.strptime(args.auth_date, "%Y-%m-%d").replace(
            hour=12, tzinfo=timezone(timedelta(hours=-5))
        )
        set_clauses = [
            "credit_status = 'INVOICED'",
            "sri_status = 'AUTHORIZED'",
            f"sri_authorization_date = ${len(params) + 1}",
            "sri_messages = NULL",
        ]
        if args.clear_sequential:
            set_clauses += ["sequential_number = NULL", "access_key = NULL"]
        update_sql = f"UPDATE dispatches SET {', '.join(set_clauses)} WHERE {where}"
        status = await conn.execute(update_sql, *params, auth_dt)
        print(f"\n{status}")

        # After-check by explicit ids (contract-mode WHERE drops the converted
        # source_status, so reusing it would return nothing).
        ids = [r["dispatch_id"] for r in rows]
        after = await conn.fetch(
            "SELECT dispatch_id, credit_status, sri_status, sri_authorization_date, "
            "sequential_number, access_key, sri_messages, key49_invoice_id "
            "FROM dispatches WHERE dispatch_id = ANY($1::int[]) ORDER BY dispatch_id",
            ids,
        )
        print("\nEstado tras el cambio:")
        for r in after[:5]:
            print(f"  #{r['dispatch_id']} credit_status={r['credit_status']} "
                  f"sri={r['sri_status']} auth={r['sri_authorization_date']:%Y-%m-%d} "
                  f"seq={r['sequential_number']}")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
