"""Recover un-invoiced dispatches (SRI/Key49 PENDING) after an outage.

CONTEXT
-------
Between 2026-09-03 15:37 and the plan renewal, Key49 answered HTTP 402
PLAN_EXPIRED for every invoice request, so ~1.4k dispatches never got an
electronic invoice. The normal retry (``retry_pending_invoices``) skips — and
marks FAILED — anything older than 24h, because the SRI rejects invoices whose
``issue_date`` is not today.

The PENDING set is NOT homogeneous. Before touching anything, this tool
classifies it (see ``--report``) into:

* **already_in_key49** — ``key49_invoice_id`` is set: the invoice exists at
  Key49, our DB status is just stale. Do NOT re-emit (would duplicate).
  Use ``--sync-existing`` to refresh their status from Key49.
* **missing** — no ``key49_invoice_id``. Reconcile by ``access_key`` against
  Key49 and, if absent there too, re-emit with a **fresh access key dated
  today** so it passes SRI validation.
* ``CANCELLED`` and ``PENDING_BULK_INVOICE`` (public sector, handled by the
  global/bulk invoice flow) are always excluded.

SAFETY MODEL
------------
* **DRY-RUN by default.** Nothing is sent and no DB row is written unless
  ``--execute`` is passed.
* Reconciliation re-checks Key49 before every re-emission (by
  ``key49_invoice_id`` and by ``GET /v1/invoices?access_key=...``).
* ``--limit`` caps how many rows are processed per run.
* JSON report written to ``--report`` (default ``/tmp/k49_recovery.json``).

RECOMMENDED FLOW
----------------
1. Classify (no API calls)::

       python scripts/recover_pending_invoices.py --classify-only

2. Dry-run a batch and review::

       python scripts/recover_pending_invoices.py --limit 5

3. Small live batch::

       python scripts/recover_pending_invoices.py --limit 5 --execute

4. Sync stale statuses (already invoiced at Key49)::

       python scripts/recover_pending_invoices.py --sync-existing --limit 50 --execute

DB CONNECTION
-------------
Runs against whatever the app is configured for. For production::

    DATABASE_HOST=100.97.47.123 DATABASE_PORT=5432 \\
    DATABASE_NAME=powerfin_gas DATABASE_USER=agent_llm \\
    DATABASE_PASSWORD=... PYTHONPATH=. \\
    python scripts/recover_pending_invoices.py ...
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select

from app.config import ECUADOR_TZ
from app.database import async_session
from app.models.company import CompanyInfo
from app.models.dispatch import Dispatch
from app.models.tributary import EmissionPoint
from app.services.access_key_service import generate_access_key
from app.services.key49_service import _get_key49_config, emitir_factura


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--execute", action="store_true", help="Actually write/send (default: dry-run)")
    p.add_argument("--limit", type=int, default=25, help="Max rows per run (default 25)")
    p.add_argument("--min-age-hours", type=float, default=24.0,
                   help="Only touch dispatches older than this (default 24; 0 = all)")
    p.add_argument("--month", help="Only rows in YYYY-MM (e.g. 2026-09)")
    p.add_argument("--dispatch-id", type=int, action="append",
                   help="Specific dispatch id (repeatable; bypasses age/month filters)")
    p.add_argument("--order", choices=["oldest", "newest"], default="oldest")
    p.add_argument("--no-reconcile", action="store_true", help="Skip Key49 access_key checks")
    p.add_argument("--classify-only", action="store_true", help="Only print the classification, no API calls")
    p.add_argument("--sync-existing", action="store_true",
                   help="Refresh status of dispatches already present at Key49")
    p.add_argument("--delay", type=float, default=2.5,
                   help="Seconds between live emissions to respect Key49 rate limit (default 2.5)")
    p.add_argument("--report", default="/tmp/k49_recovery.json", help="JSON report output path")
    return p.parse_args(argv)


async def _load_company(db):
    return (await db.execute(select(CompanyInfo).limit(1))).scalar_one_or_none()


async def _load_ep(db, ep_id, cache):
    if ep_id is None:
        return None
    if ep_id not in cache:
        cache[ep_id] = (await db.execute(
            select(EmissionPoint).where(EmissionPoint.emission_point_id == ep_id)
        )).scalar_one_or_none()
    return cache[ep_id]


def _regen_access_key(dispatch: Dispatch, ep: EmissionPoint, company: CompanyInfo) -> str | None:
    """Regenerate the SRI access key with TODAY's date (SRI requires today)."""
    if not dispatch.sequential_number or not company.ruc or not company.sri_environment:
        return None
    parts = dispatch.sequential_number.split("-")
    try:
        seq = int(parts[-1]) if len(parts) >= 3 else int(dispatch.sequential_number)
    except (ValueError, TypeError):
        return None
    return generate_access_key(
        emission_date=datetime.now(ECUADOR_TZ).date(),
        doc_type=ep.doc_type or "FACTURA",
        ruc=company.ruc,
        sri_environment=company.sri_environment,
        establishment=ep.establishment,
        emission_point=ep.emission_point,
        sequential=seq,
        emission_type=company.emission_type or 1,
    )


def _by_month(dispatches: list[Dispatch]) -> dict:
    out: dict[str, int] = {}
    for d in dispatches:
        key = d.created_at.strftime("%Y-%m") if d.created_at else "?"
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))


def _apply_month_filter(dispatches: list[Dispatch], month: str | None) -> list[Dispatch]:
    if not month:
        return dispatches
    return [d for d in dispatches if d.created_at and d.created_at.strftime("%Y-%m") == month]


def _candidate_filter(args, dispatches: list[Dispatch]) -> list[Dispatch]:
    if args.dispatch_id:
        wanted = set(args.dispatch_id)
        return [d for d in dispatches if d.dispatch_id in wanted]
    cutoff = datetime.now(ECUADOR_TZ) - timedelta(hours=args.min_age_hours)
    sel = [d for d in dispatches if d.created_at and d.created_at < cutoff]
    sel.sort(key=lambda d: d.created_at, reverse=(args.order == "newest"))
    return sel[: args.limit]


async def _reconcile_by_access_key(client, config, access_keys) -> dict:
    found: dict[str, dict] = {}
    for ak in access_keys:
        if not ak:
            continue
        try:
            r = await client.get(
                f"{config['base_url']}/invoices",
                params={"access_key": ak},
                headers={"Authorization": f"Bearer {config['api_key']}"},
            )
            if r.status_code != 200:
                continue
            rows = r.json().get("data") or []
            if rows:
                found[ak] = rows[0]
        except httpx.HTTPError:
            continue
    return found


async def _sync_existing(db, client, config, dispatch: Dispatch, execute: bool) -> dict:
    """Refresh one already-invoiced dispatch from Key49 by key49_invoice_id."""
    if not dispatch.key49_invoice_id:
        return {"dispatch_id": dispatch.dispatch_id, "result": "SYNC_NO_ID"}
    try:
        r = await client.get(
            f"{config['base_url']}/invoices/{dispatch.key49_invoice_id}",
            headers={"Authorization": f"Bearer {config['api_key']}"},
        )
    except httpx.HTTPError as exc:
        return {"dispatch_id": dispatch.dispatch_id, "result": "SYNC_ERROR", "error": str(exc)}
    if r.status_code != 200:
        return {"dispatch_id": dispatch.dispatch_id, "result": f"SYNC_HTTP_{r.status_code}"}

    data = r.json()["data"]
    new_status = data.get("status")
    if execute:
        dispatch.sri_status = new_status
        if data.get("access_key"):
            dispatch.key49_access_key = data["access_key"]
            dispatch.access_key = data["access_key"]
        if new_status in ("AUTHORIZED", "NOTIFIED"):
            auth_raw = data.get("authorization_date")
            if auth_raw:
                try:
                    dispatch.sri_authorization_date = datetime.fromisoformat(auth_raw)
                except ValueError:
                    dispatch.sri_authorization_date = datetime.now(ECUADOR_TZ)
            else:
                dispatch.sri_authorization_date = datetime.now(ECUADOR_TZ)
        msgs = data.get("sri_messages") or []
        dispatch.sri_messages = (
            json.dumps([m.get("message", "") for m in msgs])[:500] if msgs else None
        )
        await db.commit()
    return {"dispatch_id": dispatch.dispatch_id, "order_id": dispatch.order_id,
            "result": "SYNCED" if execute else "WOULD_SYNC", "new_status": new_status}


async def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    mode = "EXECUTE" if args.execute else "DRY-RUN"
    print(f"=== Key49 pending recovery — {mode} ===")
    print(f"limit={args.limit} min_age_hours={args.min_age_hours} month={args.month} "
          f"order={args.order} reconcile={not args.no_reconcile} "
          f"sync_existing={args.sync_existing}\n")

    report: dict = {"mode": mode, "started_at": datetime.now(ECUADOR_TZ).isoformat(),
                    "classification": {}, "items": [], "summary": {}}

    async with async_session() as db:
        config = await _get_key49_config(db)
        company = await _load_company(db)
        if company is None:
            print("ERROR: no company_info row")
            return 2

        rows = (await db.execute(
            select(Dispatch).where(
                Dispatch.sri_status == "PENDING",
                Dispatch.status != "CANCELLED",
                Dispatch.credit_status.is_distinct_from("PENDING_BULK_INVOICE"),
            )
        )).scalars().all()

        already = [d for d in rows if d.key49_invoice_id]
        missing = [d for d in rows if not d.key49_invoice_id]

        report["classification"] = {
            "total_pending": len(rows),
            "already_in_key49": len(already),
            "missing": len(missing),
            "already_in_key49_by_month": _by_month(already),
            "missing_by_month": _by_month(missing),
        }
        print("CLASIFICACIÓN:")
        print(f"  total PENDING (excl. bulk/cancelled): {len(rows)}")
        print(f"  ya en Key49 (solo sincronizar estado): {len(already)} {_by_month(already)}")
        print(f"  sin factura (reemitir):                {len(missing)} {_by_month(missing)}\n")

        if args.classify_only:
            with open(args.report, "w", encoding="utf-8") as fh:
                json.dump(report, fh, indent=2, ensure_ascii=False)
            print(f"Reporte: {args.report}")
            return 0

        ep_cache: dict = {}
        sent = skipped = failed = synced = 0

        async with httpx.AsyncClient(timeout=15.0) as client:
            # ── 1. Sync statuses of rows already at Key49 ─────────────
            if args.sync_existing:
                sync_rows = _candidate_filter(args, _apply_month_filter(already, args.month))
                print(f"SINCRONIZAR estado de {len(sync_rows)} ya-invoiced…")
                for d in sync_rows:
                    item = await _sync_existing(db, client, config, d, args.execute)
                    report["items"].append(item)
                    print(f"  #{d.dispatch_id} {d.order_id}: {item['result']} "
                          f"{item.get('new_status', '')}")
                    synced += 1

            # ── 2. Re-emit missing ────────────────────────────────────
            candidates = _candidate_filter(args, _apply_month_filter(missing, args.month))
            print(f"\nREEMITIR {len(candidates)} sin factura "
                  f"(de {len(missing)} totales)")

            already_at_key49: dict = {}
            if candidates and not args.no_reconcile:
                keys = {d.access_key for d in candidates} | {d.key49_access_key for d in candidates}
                already_at_key49 = await _reconcile_by_access_key(client, config, keys)
                print(f"  reconciliación: {len(already_at_key49)} ya están en Key49 → skip")

            for d in candidates:
                ep = await _load_ep(db, d.emission_point_id, ep_cache)
                if ep is None:
                    report["items"].append({"dispatch_id": d.dispatch_id, "order_id": d.order_id,
                                            "result": "SKIP_NO_EMISSION_POINT"})
                    print(f"  #{d.dispatch_id} {d.order_id}: SKIP (sin punto de emisión)")
                    skipped += 1
                    continue

                hit = already_at_key49.get(d.access_key) or already_at_key49.get(d.key49_access_key)
                if hit:
                    report["items"].append({"dispatch_id": d.dispatch_id, "order_id": d.order_id,
                                            "result": "ALREADY_AT_KEY49", "key49_status": hit.get("status")})
                    print(f"  #{d.dispatch_id} {d.order_id}: YA EN KEY49 ({hit.get('status')}) — skip")
                    skipped += 1
                    continue

                new_key = _regen_access_key(d, ep, company)
                if not new_key:
                    report["items"].append({"dispatch_id": d.dispatch_id, "order_id": d.order_id,
                                            "result": "SKIP_CANNOT_REGEN_KEY"})
                    print(f"  #{d.dispatch_id} {d.order_id}: SKIP (no se pudo regenerar clave)")
                    failed += 1
                    continue

                if not args.execute:
                    report["items"].append({"dispatch_id": d.dispatch_id, "order_id": d.order_id,
                                            "result": "WOULD_EMIT", "new_access_key": new_key})
                    print(f"  #{d.dispatch_id} {d.order_id}: emitiría con clave {new_key[:8]}…")
                    sent += 1
                    continue

                d.access_key = new_key
                await db.commit()
                ok = await emitir_factura(db, d.dispatch_id)
                report["items"].append({"dispatch_id": d.dispatch_id, "order_id": d.order_id,
                                        "result": "EMITTED" if ok else "EMIT_FAILED",
                                        "new_access_key": new_key})
                print(f"  #{d.dispatch_id} {d.order_id}: {'EMITIDA' if ok else 'FALLÓ'}")
                sent += 1 if ok else 0
                failed += 0 if ok else 1
                if args.delay > 0:
                    await asyncio.sleep(args.delay)

        if args.execute and (sent or synced):
            print("\nEsperando polling de autorización (30s)…")
            await asyncio.sleep(30)

    report["summary"] = {"candidates_missing": len(missing), "already_in_key49": len(already),
                         "emitted_or_would": sent, "skipped": skipped, "failed": failed,
                         "synced": synced}
    report["finished_at"] = datetime.now(ECUADOR_TZ).isoformat()
    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)

    print(f"\n=== RESUMEN — {mode} ===")
    print(json.dumps(report["summary"], indent=2))
    print(f"Reporte: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:])))
