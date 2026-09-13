#!/usr/bin/env python3
"""Clear invalid identifications so the POS is forced to re-capture them.

Why: Key49 rejects cédulas with a bad check digit ("Invalid identification for
type 05") and RUCs that do not exist in the SRI registry ("type 04") *after* the
sale was paid. Keeping the wrong number means the failure repeats forever,
because the POS finds the customer by that number and proceeds.

What it does (per person):
  * CED with an invalid module-10 check digit        → id_number = NULL
  * RUC the SRI registry does not know (broker 404)   → id_number = NULL

Person is NOT deactivated: plates, history, price list and credit contracts stay
linked. Only the identification is blanked, so the POS must ask the customer for
it again (see `pos_backend/app/services/id_validation.py`).

Safety
------
* `--dry-run` (default) prints the plan and touches nothing.
* `--apply` writes, and first copies every affected row into
  `persons_invalid_id_backup` (created on the fly, one row per run).
* Idempotent: rows already cleared are skipped.
* RUC verification uses the SRI registry through the identity API. RUCs that the
  registry confirms are NEVER cleared, even if the module-11 check digit fails
  (that check digit is unreliable — see the module docstring).

Usage
-----
    cd pos_backend && source venv/bin/activate
    python ../scripts/limpiar_ids_invalidos.py                 # dry-run (prod)
    python ../scripts/limpiar_ids_invalidos.py --apply
    python ../scripts/limpiar_ids_invalidos.py --apply --include-ced
    python ../scripts/limpiar_ids_invalidos.py --dsn postgresql://...

Environment: DSN defaults to the production read/write user from docs/DB_ACCESS.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pos_backend"))

from app.services.id_validation import cedula_error, ruc_error  # noqa: E402

DEFAULT_DSN = "postgresql://agent_llm:AgentLLM123@100.97.47.123:5432/powerfin_gas"

IDENTITY_API_URL = "http://131.161.221.131:2356"
IDENTITY_API_TOKEN = os.environ.get(
    "IDENTITY_API_TOKEN",
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJnYXMiLCJ1c2VySWQiOjUsImVtYWlsIjoiZ2FzQGRhdGFnby5jb20iLCJmdWxsTmFtZSI6IlBvd2VyZmluIFBPUyBHQVMgSW50ZWdyYXRpb24iLCJyb2xlcyI6WyJBUElfQ0xJRU5UIl0sImlhdCI6MTc4MDQyODI3OSwiZXhwIjoxODExOTY0Mjc5fQ.fYSb--was6n089W-CCZUzY2vSL7qYKt1VUq_eiaYLtA",
)

BACKUP_DDL = """
CREATE TABLE IF NOT EXISTS persons_invalid_id_backup (
    backup_id     serial PRIMARY KEY,
    run_at        timestamptz NOT NULL DEFAULT now(),
    person_id     integer     NOT NULL,
    id_type       varchar(5),
    old_id_number varchar(13),
    reason        text,
    name          varchar(200)
)
"""


def _sri_lookup(ruc: str, timeout: int = 20) -> tuple[str, str]:
    """Return (status, message) for a RUC against the SRI registry.

    'OK'        → exists, never clear it
    'NOT_FOUND' → the registry does not know it → clear it
    'ERROR'     → provider down → do NOT clear it (never guess)
    """
    url = f"{IDENTITY_API_URL}/v1/info/ALL/sri/{ruc}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {IDENTITY_API_TOKEN}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as exc:
        try:
            data = json.loads(exc.read().decode())
        except Exception:
            return "ERROR", f"HTTP {exc.code}"
    except Exception as exc:  # network / provider down
        return "ERROR", str(exc)[:120]

    status = str(data.get("httpStatus") or "")
    if status == "OK":
        return "OK", ""
    if status == "NOT_FOUND":
        return "NOT_FOUND", str(data.get("message") or "")
    return "ERROR", f"{status}: {data.get('message')}"


async def _load_persons(dsn: str):
    import asyncpg

    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(
            """
            SELECT person_id, id_type, id_number, name
            FROM persons
            WHERE is_active = true AND id_number IS NOT NULL
            ORDER BY person_id
            """
        )
        # A RUC can pass the local structure rules and still not exist in the
        # SRI registry (see id_validation docstring). Those are only discoverable
        # through the registry — or through their own failed invoices.
        rejected = await conn.fetch(
            """
            SELECT DISTINCT p.person_id, p.id_type, p.id_number, p.name
            FROM persons p
            JOIN dispatches d ON d.person_id = p.person_id
            WHERE p.is_active = true AND p.id_type = 'RUC' AND p.id_number IS NOT NULL
              AND d.status <> 'CANCELLED'
              AND d.sri_messages LIKE '%Invalid identification%'
            """
        )
    finally:
        await conn.close()
    return [dict(r) for r in rows], [dict(r) for r in rejected]


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dsn", default=os.environ.get("DSN", DEFAULT_DSN))
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    parser.add_argument("--include-ced", action="store_true", default=True,
                        help="include cédulas with a bad check digit (default: true)")
    parser.add_argument("--no-ced", dest="include_ced", action="store_false")
    parser.add_argument("--verify-ruc-registry", action="store_true", default=True,
                        help="confirm RUCs against the SRI registry (default: true)")
    parser.add_argument("--no-verify-ruc-registry", dest="verify_ruc_registry", action="store_false")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()

    persons, historically_rejected = await _load_persons(args.dsn)
    print(f"Personas activas con identificación: {len(persons)}")

    ced_bad = [p for p in persons if p["id_type"] == "CED" and cedula_error(p["id_number"])]

    # RUC candidates: locally suspicious OR already rejected by Key49 for the
    # identification itself (catches registry-unknown RUCs that pass the
    # structure rules).
    ruc_suspect_by_id = {}
    for p in persons:
        if p["id_type"] == "RUC" and ruc_error(p["id_number"]):
            ruc_suspect_by_id[p["person_id"]] = p
    for p in historically_rejected:
        ruc_suspect_by_id.setdefault(p["person_id"], p)
    ruc_suspect = list(ruc_suspect_by_id.values())

    print(f"  cédulas con dígito verificador inválido : {len(ced_bad)}")
    print(f"  RUC a verificar contra el registro SRI  : {len(ruc_suspect)}")

    ruc_bad: list[dict] = []
    ruc_unknown_status: list[dict] = []
    if ruc_suspect:
        if args.verify_ruc_registry:
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                results = list(pool.map(lambda p: _sri_lookup(p["id_number"]), ruc_suspect))
            for person, (status, message) in zip(ruc_suspect, results):
                person["_sri_status"] = status
                person["_sri_message"] = message
                if status == "NOT_FOUND":
                    ruc_bad.append(person)
                elif status == "ERROR":
                    ruc_unknown_status.append(person)
        else:
            ruc_bad = list(ruc_suspect)

    targets = []
    if args.include_ced:
        for p in ced_bad:
            p["_reason"] = f"CED inválida: {cedula_error(p['id_number'])}"
            targets.append(p)
    for p in ruc_bad:
        p["_reason"] = f"RUC no existe en el SRI: {p.get('_sri_message', '')}".strip()
        targets.append(p)

    print()
    print(f"→ A limpiar: {len(targets)}")
    for p in targets:
        print(f"   {p['person_id']:>6}  {p['id_type']:3} {p['id_number']:<14} {p['name'][:38]:<38} {p['_reason'][:60]}")

    if ruc_unknown_status:
        print()
        print(f"⚠ No se pudo verificar {len(ruc_unknown_status)} RUC (servicio SRI caído) — NO se limpian:")
        for p in ruc_unknown_status:
            print(f"   {p['person_id']:>6}  {p['id_number']:<14} {p['name'][:38]} {p['_sri_message'][:50]}")

    if not targets:
        print("\nNada que hacer.")
        return 0

    if not args.apply:
        print("\nDRY-RUN — nada se modificó. Repita con --apply para aplicar.")
        return 0

    import asyncpg

    conn = await asyncpg.connect(args.dsn)
    try:
        await conn.execute(BACKUP_DDL)
        run_at = datetime.now(timezone.utc)
        for p in targets:
            await conn.execute(
                """
                INSERT INTO persons_invalid_id_backup
                    (run_at, person_id, id_type, old_id_number, reason, name)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                run_at, p["person_id"], p["id_type"], p["id_number"], p["_reason"], p["name"],
            )
        ids = [p["person_id"] for p in targets]
        cleared = await conn.execute(
            "UPDATE persons SET id_number = NULL WHERE person_id = ANY($1::int[])", ids
        )
        print(f"\n✅ Respaldo en persons_invalid_id_backup (run_at={run_at.isoformat()})")
        print(f"✅ {cleared} — {len(targets)} personas quedan sin identificación.")
        print("   El POS pedirá la cédula/RUC de nuevo antes de la próxima venta.")
    finally:
        await conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
