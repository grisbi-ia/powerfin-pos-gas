"""Admin SRI/Key49 monitoring API — READ-ONLY (Phase 1).

Gated by ``system_config['sri_monitor_enabled']`` (default off). When the flag
is absent/false every endpoint returns 403, so the module executes zero new
queries and cannot affect the production sale flow.

Permissions: require_permission("sri", "read") + ADMIN/SUPERVISOR role.
"""

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.deps import get_admin_user, require_permission
from app.config import ECUADOR_TZ
from app.database import get_db
from app.models.company import SystemConfig
from app.services import sri_monitor_service as svc
from app.services.export_service import generate_excel, generate_pdf

router = APIRouter(
    prefix="/api/admin/sri",
    tags=["admin-sri"],
    dependencies=[Depends(get_admin_user)],
)


async def require_sri_monitor_enabled(db: AsyncSession = Depends(get_db)) -> None:
    """Feature flag gate — the whole monitoring module ships disabled."""
    cfg = (await db.execute(
        select(SystemConfig).where(SystemConfig.key == "sri_monitor_enabled")
    )).scalar_one_or_none()
    if cfg is None or (cfg.value or "").strip().lower() != "true":
        raise HTTPException(
            status_code=403,
            detail="Módulo de monitoreo SRI desactivado (system_config: sri_monitor_enabled)",
        )


def _default_range() -> tuple[date, date]:
    today = date.today()
    return today - timedelta(days=29), today


@router.get("/metrics", dependencies=[Depends(require_sri_monitor_enabled)])
async def sri_metrics(
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    emission_point_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_permission("sri", "read")),
):
    """KPI + time-series metrics of the SRI/Key49 pipeline."""
    df, dt = (date_from, date_to) if date_from and date_to else _default_range()
    return await svc.get_metrics(db, df, dt, emission_point_id)


@router.get("/documents", dependencies=[Depends(require_sri_monitor_enabled)])
async def sri_documents(
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    status: str | None = Query(default=None),
    problem_type: str | None = Query(default=None),
    search: str = Query(default=""),
    only_problems: bool = Query(default=True),
    key49: str | None = Query(default=None, pattern=r"^(yes|no)$",
                              description="Filter by presence in Key49"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_permission("sri", "read")),
):
    """Paginated documents with SRI problems (default) or a status filter."""
    items, total = await svc.list_documents(
        db, date_from, date_to, status, problem_type, search,
        only_problems, page, page_size, key49_filter=key49,
    )
    summary = await svc.documents_summary(
        db, date_from, date_to, status, problem_type, search,
        only_problems, key49_filter=key49,
    )
    pages = (total + page_size - 1) // page_size if page_size else 0
    return {"items": items, "total": total, "page": page,
            "page_size": page_size, "pages": pages, "summary": summary}


@router.get("/documents/{dispatch_id}", dependencies=[Depends(require_sri_monitor_enabled)])
async def sri_document_detail(
    dispatch_id: int,
    live: bool = Query(default=True, description="Include a live Key49 read"),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_permission("sri", "read")),
):
    """Full detail of one document, optionally enriched from Key49."""
    detail = await svc.get_document_detail(db, dispatch_id, live=live)
    if detail is None:
        raise HTTPException(status_code=404, detail="Despacho no encontrado")
    return detail


@router.get("/health", dependencies=[Depends(require_sri_monitor_enabled)])
async def sri_health(
    probe: bool = Query(default=False, description="Live Key49 connectivity probe"),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_permission("sri", "read")),
):
    """Key49 configuration + recent error signal (+ optional live probe)."""
    return await svc.get_health(db, probe=probe)


@router.post("/documents/export", dependencies=[Depends(require_sri_monitor_enabled)])
async def sri_documents_export(
    format: str = Query("xlsx", pattern=r"^(pdf|xlsx)$"),
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    status: str | None = Query(default=None),
    problem_type: str | None = Query(default=None),
    search: str = Query(default=""),
    only_problems: bool = Query(default=True),
    key49: str | None = Query(default=None, pattern=r"^(yes|no)$"),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_permission("sri", "read")),
):
    """Export the problem-document inbox to PDF or Excel."""
    items, _total = await svc.list_documents(
        db, date_from, date_to, status, problem_type, search,
        only_problems, page=1, page_size=5000, key49_filter=key49,
    )

    columns = ["Fecha", "Order ID", "Cliente", "Cédula/RUC", "Placa",
               "Total", "Estado SRI", "Tipo problema", "En Key49",
               "Secuencial", "Key49 ID"]
    rows = []
    for it in items:
        created = it.get("created_at")
        fecha = ""
        if created:
            try:
                fecha = (
                    datetime.fromisoformat(created)
                    .astimezone(ECUADOR_TZ).strftime("%d/%m/%Y %H:%M")
                )
            except ValueError:
                fecha = created
        rows.append([
            fecha, it.get("order_id") or "", it.get("customer_name") or "",
            it.get("id_number") or "", it.get("plate") or "",
            f"${it.get('total', 0):,.2f}", it.get("sri_status") or "",
            it.get("problem_type") or "",
            "Sí" if it.get("has_key49_id") else "No",
            it.get("sequential_number") or "",
            it.get("key49_invoice_id") or "",
        ])

    if format == "pdf":
        data = generate_pdf("Documentos SRI con problemas", columns, rows)
        media = "application/pdf"
        ext = "pdf"
    else:
        data = generate_excel("Documentos SRI con problemas", columns, rows)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ext = "xlsx"

    return Response(content=data, media_type=media,
                    headers={"Content-Disposition": f"attachment; filename=documentos_sri.{ext}"})
