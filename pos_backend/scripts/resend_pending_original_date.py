#!/usr/bin/env python3
"""Resend a PENDING dispatch to Key49 WITHOUT changing the issue date nor
regenerating the access key (uses the ones already stored on the dispatch).

Purpose: test whether Key49/SRI accepts an invoice whose access key encodes a
PAST date. The normal recovery tool (``recover_pending_invoices.py``) always
regenerates the access key with today's date; this one does not.

DRY-RUN by default (builds the payload and checks Key49 by access_key).
``--execute`` performs the POST and, if Key49 accepts (HTTP 202), persists
``key49_invoice_id`` so the background reconciler closes it to NOTIFIED.

Run from ``pos_backend`` against the target DB:

    DATABASE_HOST=100.97.47.123 DATABASE_PORT=5432 DATABASE_NAME=powerfin_gas \
    DATABASE_USER=agent_llm DATABASE_PASSWORD=... PYTHONPATH=. \
      python scripts/resend_pending_original_date.py --dispatch-id 22073 [--execute]
"""

import argparse
import asyncio
import json
import sys

import httpx
from sqlalchemy import select

from app.config import ECUADOR_TZ
from app.database import async_session
from app.models.dispatch import Dispatch
from app.services.key49_service import (
    _build_invoice_payload,
    _get_key49_config,
    _key49_error_message,
)


async def main(dispatch_id: int, execute: bool) -> int:
    async with async_session() as db:
        dispatch = (
            await db.execute(
                select(Dispatch).where(Dispatch.dispatch_id == dispatch_id)
            )
        ).scalar_one_or_none()
        if not dispatch:
            print(f"ABORT: dispatch {dispatch_id} no existe")
            return 2

        print(
            f"dispatch {dispatch_id}: seq={dispatch.sequential_number} "
            f"status={dispatch.status} sri_status={dispatch.sri_status} "
            f"total={dispatch.total}"
        )
        print(f"created_at={dispatch.created_at}  access_key={dispatch.access_key}")

        if dispatch.sri_status not in (None, "PENDING"):
            print(f"ABORT: sri_status={dispatch.sri_status} — no está PENDING")
            return 2
        if dispatch.key49_invoice_id:
            print(f"ABORT: ya tiene key49_invoice_id={dispatch.key49_invoice_id}")
            return 2
        if not dispatch.access_key:
            print("ABORT: el dispatch no tiene access_key guardado")
            return 2

        payload = await _build_invoice_payload(db, dispatch)
        if not payload:
            print("ABORT: no se pudo construir el payload (datos insuficientes)")
            return 2

        # Force the ORIGINAL issue date (access_key was generated with it).
        orig_date = dispatch.created_at.astimezone(ECUADOR_TZ).strftime("%Y-%m-%d")
        payload["issue_date"] = orig_date

        ak = payload["access_key"]
        print(
            f"issue_date forzado -> {orig_date} "
            f"(access_key[0:8]={ak[:8]} = ddmmaaaa)"
        )

        config = await _get_key49_config(db)
        if not config["api_key"]:
            print("ABORT: key49_api_key no configurada")
            return 2

        async with httpx.AsyncClient(timeout=20.0) as client:
            # Safety: is the invoice already in Key49 under this access_key?
            pre = await client.get(
                f"{config['base_url']}/invoices",
                params={"access_key": ak},
                headers={"Authorization": f"Bearer {config['api_key']}"},
            )
            print(f"\n[pre-check] GET /invoices?access_key=… -> HTTP {pre.status_code}")
            print(pre.text[:800])

            print("\n[payload]")
            print(json.dumps(payload, indent=2, ensure_ascii=False))

            if not execute:
                print("\nDRY-RUN: no se envió. Repetir con --execute para emitir.")
                return 0

            resp = await client.post(
                f"{config['base_url']}/invoices",
                headers={
                    "Authorization": f"Bearer {config['api_key']}",
                    "Content-Type": "application/json",
                    "X-Idempotency-Key": f"manual-origdate-{dispatch_id}",
                },
                json=payload,
            )
            print(f"\n[POST] HTTP {resp.status_code}")
            print(resp.text[:1500])

            if resp.status_code == 202:
                data = resp.json().get("data", {})
                dispatch.key49_invoice_id = data.get("id")
                dispatch.key49_access_key = data.get("access_key")
                dispatch.sri_status = data.get("status", "CREATED")
                dispatch.sri_messages = None
                await db.commit()
                print(
                    f"\nACEPTADA por Key49: id={dispatch.key49_invoice_id} "
                    f"status={dispatch.sri_status}"
                )
                print("El reconciler de fondo (120 s) la cerrará a NOTIFIED/AUTHORIZED.")
                return 0

            print(f"\nRECHAZADA: {_key49_error_message(resp)}")
            return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dispatch-id", type=int, required=True)
    parser.add_argument(
        "--execute", action="store_true", help="Enviar de verdad (default: dry-run)"
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.dispatch_id, args.execute)))
