"""SRI / Key49 monitoring service — READ-ONLY observability (Phase 1).

Provides metrics, a problem-document inbox, live document detail and a health
check for the electronic invoicing pipeline.

IMPORTANT — non-invasive by design:
  * This module only READS the database. It never writes and never calls
    ``emitir_factura`` / any code path used by the sale flow.
  * The whole module is gated by ``system_config['sri_monitor_enabled']``
    (default: absent/off), enforced at the API layer.
  * A live Key49 probe is opt-in and has a short timeout, wrapped in
    try/except so it can never break a request.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import httpx
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ECUADOR_TZ
from app.models.company import SystemConfig
from app.models.dispatch import Dispatch
from app.models.person import Person, Vehicle
from app.models.tributary import EmissionPoint

FINAL_OK = ("AUTHORIZED", "NOTIFIED")
IN_PROGRESS = ("CREATED", "SIGNED", "SENT", "RECEIVED")
PROBLEM_STATUSES = ("PENDING", "FAILED", "REJECTED")


def classify_problem(sri_status: str | None, has_key49_id: bool) -> str:
    """Map (sri_status, has key49 id) to a human-actionable problem type.

    Types mirror the real failure taxonomy discovered during the
    PLAN_EXPIRED recovery:
      NEVER_SENT   -> never reached Key49 (no key49 id)
      PENDING_SENT -> has a Key49 id but our status is still PENDING (stale)
      KEY49_FAILED -> Key49 exhausted retries (needs Key49-side reprocess)
      INVALID_DATA -> failed before/at validation (e.g. bad CED/RUC)
      REJECTED     -> rejected by the SRI
      IN_PROGRESS  -> CREATED/SIGNED/SENT/RECEIVED
      OK           -> AUTHORIZED/NOTIFIED
    """
    s = (sri_status or "").upper()
    if s in FINAL_OK:
        return "OK"
    if s in IN_PROGRESS:
        return "IN_PROGRESS"
    if s == "REJECTED":
        return "REJECTED"
    if s == "FAILED":
        return "KEY49_FAILED" if has_key49_id else "INVALID_DATA"
    if s == "PENDING":
        return "PENDING_SENT" if has_key49_id else "NEVER_SENT"
    return "OTHER"


def _date_conditions(date_from: date | None, date_to: date | None, emission_point_id: int | None):
    conds = [Dispatch.sri_status.isnot(None)]
    if date_from is not None:
        conds.append(func.date(Dispatch.created_at) >= date_from)
    if date_to is not None:
        conds.append(func.date(Dispatch.created_at) <= date_to)
    if emission_point_id is not None:
        conds.append(Dispatch.emission_point_id == emission_point_id)
    return conds


async def get_metrics(
    db: AsyncSession,
    date_from: date,
    date_to: date,
    emission_point_id: int | None = None,
) -> dict:
    """Aggregate SRI pipeline metrics for a date range."""
    conds = _date_conditions(date_from, date_to, emission_point_id)

    # Counts grouped by status, split by presence of a Key49 reference.
    agg = (await db.execute(
        select(
            Dispatch.sri_status,
            func.count().label("total"),
            func.count().filter(Dispatch.key49_invoice_id.isnot(None)).label("with_id"),
            func.count().filter(Dispatch.key49_invoice_id.is_(None)).label("without_id"),
        ).where(*conds).group_by(Dispatch.sri_status)
    )).all()

    by_status: dict[str, int] = {}
    with_id: dict[str, int] = {}
    without_id: dict[str, int] = {}
    total = 0
    for status, tot, wid, woid in agg:
        key = (status or "NULL").upper()
        by_status[key] = int(tot)
        with_id[key] = int(wid)
        without_id[key] = int(woid)
        total += int(tot)

    ok = by_status.get("AUTHORIZED", 0) + by_status.get("NOTIFIED", 0)
    in_progress = sum(by_status.get(s, 0) for s in IN_PROGRESS)
    problems = {
        "never_sent": without_id.get("PENDING", 0),
        "pending_sent": with_id.get("PENDING", 0),
        "key49_failed": with_id.get("FAILED", 0),
        "invalid_data": without_id.get("FAILED", 0),
        "rejected": by_status.get("REJECTED", 0),
    }
    problems_total = sum(problems.values())

    # Daily series
    day_rows = (await db.execute(
        select(
            func.date(Dispatch.created_at).label("day"),
            func.count().label("total"),
            func.count().filter(Dispatch.sri_status.in_(FINAL_OK)).label("ok"),
            func.count().filter(Dispatch.sri_status.in_(IN_PROGRESS)).label("in_progress"),
            func.count().filter(Dispatch.sri_status.in_(PROBLEM_STATUSES)).label("problems"),
        ).where(*conds).group_by("day").order_by("day")
    )).all()

    # Average time to authorization (seconds)
    avg_secs = (await db.execute(
        select(func.avg(
            func.extract("epoch", Dispatch.sri_authorization_date - Dispatch.created_at)
        )).where(*conds, Dispatch.sri_authorization_date.isnot(None))
    )).scalar()

    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "total": total,
        "authorized": ok,
        "in_progress": in_progress,
        "problems_total": problems_total,
        "success_rate": round(ok / total * 100, 2) if total else 0.0,
        "avg_authorization_seconds": round(float(avg_secs), 1) if avg_secs else None,
        "by_status": by_status,
        "problems": problems,
        "by_day": [
            {
                "day": r.day.isoformat() if r.day else None,
                "total": int(r.total),
                "authorized": int(r.ok),
                "in_progress": int(r.in_progress),
                "problems": int(r.problems),
            }
            for r in day_rows
        ],
    }


async def list_documents(
    db: AsyncSession,
    date_from: date | None,
    date_to: date | None,
    status_filter: str | None,
    problem_type: str | None,
    search: str,
    only_problems: bool,
    page: int,
    page_size: int,
) -> tuple[list[dict], int]:
    """Paginated list of SRI documents, defaulting to problem documents."""
    conds = _date_conditions(date_from, date_to, None)

    if status_filter:
        conds.append(Dispatch.sri_status == status_filter.upper())
    elif only_problems:
        conds.append(Dispatch.sri_status.in_(PROBLEM_STATUSES))

    if search:
        like = f"%{search.strip()}%"
        conds.append(or_(
            Dispatch.order_id.ilike(like),
            Person.name.ilike(like),
            Person.id_number.ilike(like),
            Vehicle.plate.ilike(like),
        ))

    base = (
        select(Dispatch, Person, Vehicle)
        .outerjoin(Person, Person.person_id == Dispatch.person_id)
        .outerjoin(Vehicle, Vehicle.vehicle_id == Dispatch.vehicle_id)
        .where(*conds)
    )

    total = (await db.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar() or 0

    rows = (await db.execute(
        base.order_by(Dispatch.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).all()

    items = []
    for dispatch, person, vehicle in rows:
        has_id = dispatch.key49_invoice_id is not None
        ptype = classify_problem(dispatch.sri_status, has_id)
        if problem_type and ptype != problem_type.upper():
            continue
        items.append(_document_row(dispatch, person, vehicle, ptype))

    # When filtering by problem_type in Python the page size may shrink; that
    # is acceptable for Phase 1 (read-only). Total reflects the DB filters.
    return items, int(total)


def _document_row(dispatch: Dispatch, person: Person | None, vehicle: Vehicle | None,
                  ptype: str) -> dict:
    return {
        "dispatch_id": dispatch.dispatch_id,
        "order_id": dispatch.order_id,
        "created_at": dispatch.created_at.isoformat() if dispatch.created_at else None,
        "customer_name": person.name if person else None,
        "id_number": person.id_number if person else None,
        "plate": vehicle.plate if vehicle else None,
        "total": float(dispatch.total or 0),
        "sri_status": dispatch.sri_status,
        "problem_type": ptype,
        "has_key49_id": dispatch.key49_invoice_id is not None,
        "key49_invoice_id": dispatch.key49_invoice_id,
        "key49_access_key": dispatch.key49_access_key or dispatch.access_key,
        "sequential_number": dispatch.sequential_number,
        "sri_authorization_date": (
            dispatch.sri_authorization_date.isoformat()
            if dispatch.sri_authorization_date else None
        ),
        "sri_messages": dispatch.sri_messages,
        "emission_point_id": dispatch.emission_point_id,
    }


async def get_document_detail(
    db: AsyncSession, dispatch_id: int, live: bool = False
) -> dict | None:
    """Full detail for one dispatch, optionally enriched with a live Key49 read."""
    row = (await db.execute(
        select(Dispatch, Person, Vehicle)
        .outerjoin(Person, Person.person_id == Dispatch.person_id)
        .outerjoin(Vehicle, Vehicle.vehicle_id == Dispatch.vehicle_id)
        .where(Dispatch.dispatch_id == dispatch_id)
    )).first()
    if row is None:
        return None

    dispatch, person, vehicle = row
    has_id = dispatch.key49_invoice_id is not None
    detail = _document_row(dispatch, person, vehicle,
                           classify_problem(dispatch.sri_status, has_id))

    ep = None
    if dispatch.emission_point_id:
        ep = (await db.execute(
            select(EmissionPoint).where(
                EmissionPoint.emission_point_id == dispatch.emission_point_id
            )
        )).scalar_one_or_none()
    detail["emission_point"] = (
        f"{ep.establishment}-{ep.emission_point}" if ep else None
    )

    detail["key49_live"] = None
    if live and dispatch.key49_invoice_id:
        detail["key49_live"] = await _key49_get_invoice(db, dispatch.key49_invoice_id)
    return detail


async def _key49_config(db: AsyncSession) -> dict:
    rows = (await db.execute(
        select(SystemConfig).where(SystemConfig.key.in_(
            ["key49_api_key", "key49_base_url", "key49_enabled", "sri_monitor_enabled"]
        ))
    )).scalars().all()
    cfg = {c.key: (c.value or "") for c in rows}
    return {
        "api_key": cfg.get("key49_api_key", ""),
        "base_url": cfg.get("key49_base_url", "https://key49.apx5.com/v1"),
        "enabled": cfg.get("key49_enabled", "false").lower() == "true",
        "monitor_enabled": cfg.get("sri_monitor_enabled", "false").lower() == "true",
    }


async def _key49_get_invoice(db: AsyncSession, invoice_id: str) -> dict | None:
    """Best-effort live read from Key49. Never raises."""
    cfg = await _key49_config(db)
    if not cfg["api_key"]:
        return None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{cfg['base_url']}/invoices/{invoice_id}",
                headers={"Authorization": f"Bearer {cfg['api_key']}"},
            )
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}"}
        data = resp.json().get("data", {})
        return {
            "id": data.get("id"),
            "status": data.get("status"),
            "access_key": data.get("access_key"),
            "authorization_date": data.get("authorization_date"),
            "retry_count": data.get("retry_count"),
            "sri_messages": data.get("sri_messages") or [],
        }
    except Exception as exc:  # noqa: BLE001 — diagnostics must never break a request
        return {"error": type(exc).__name__}


async def get_health(db: AsyncSession, probe: bool = False) -> dict:
    """Key49 configuration + recent error signal, optional live probe."""
    cfg = await _key49_config(db)

    since = datetime.now(ECUADOR_TZ) - timedelta(hours=24)
    err_rows = (await db.execute(
        select(Dispatch.sri_status, Dispatch.sri_messages)
        .where(Dispatch.sri_status.in_(("PENDING", "FAILED")),
               Dispatch.created_at >= since)
    )).all()
    plan_expired = unavailable = http_402 = 0
    for _status, msgs in err_rows:
        text = (msgs or "")
        if "PLAN_EXPIRED" in text:
            plan_expired += 1
        if "no disponible" in text:
            unavailable += 1
        if "402" in text:
            http_402 += 1

    health = {
        "key49_configured": bool(cfg["api_key"]),
        "key49_enabled": cfg["enabled"],
        "base_url": cfg["base_url"],
        "last_24h": {
            "plan_expired": plan_expired,
            "unavailable": unavailable,
            "http_402": http_402,
        },
        "probe": None,
    }

    if probe and cfg["api_key"]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{cfg['base_url']}/invoices",
                    params={"per_page": 1},
                    headers={"Authorization": f"Bearer {cfg['api_key']}"},
                )
            body = {}
            try:
                body = resp.json()
            except Exception:  # noqa: BLE001
                body = {}
            health["probe"] = {
                "status_code": resp.status_code,
                "ok": resp.status_code == 200,
                "error_code": (body.get("error") or {}).get("code"),
                "error_message": (body.get("error") or {}).get("message"),
            }
        except Exception as exc:  # noqa: BLE001
            health["probe"] = {"ok": False, "error": type(exc).__name__}

    return health
