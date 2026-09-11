"""Export un-invoiced dispatches (SRI PENDING, never sent) to Excel.

For accounting review of sales that never reached Key49/SRI.

Usage (from pos_backend, venv active, prod DB env vars set):
    PYTHONPATH=. python scripts/export_uninvoiced.py [output.xlsx]

Selects: dispatches with sri_status='PENDING', no key49_invoice_id,
status='COLLECTED', excluding PENDING_BULK_INVOICE (public sector).
"""
import asyncio
import sys
from datetime import datetime

from sqlalchemy import select

from app.config import ECUADOR_TZ
from app.database import async_session
from app.models.dispatch import Dispatch, DispatchDetail
from app.models.person import Person, Vehicle
from app.models.product import Product
from app.services.export_service import generate_excel


async def main(out_path: str) -> None:
    async with async_session() as db:
        rows = (await db.execute(
            select(Dispatch).where(
                Dispatch.sri_status == "PENDING",
                Dispatch.key49_invoice_id.is_(None),
                Dispatch.status == "COLLECTED",
                Dispatch.credit_status.is_distinct_from("PENDING_BULK_INVOICE"),
            ).order_by(Dispatch.created_at)
        )).scalars().all()

        person_ids = {d.person_id for d in rows if d.person_id}
        vehicle_ids = {d.vehicle_id for d in rows if d.vehicle_id}
        persons = {p.person_id: p for p in (await db.execute(
            select(Person).where(Person.person_id.in_(person_ids))
        )).scalars().all()} if person_ids else {}
        vehicles = {v.vehicle_id: v for v in (await db.execute(
            select(Vehicle).where(Vehicle.vehicle_id.in_(vehicle_ids))
        )).scalars().all()} if vehicle_ids else {}

        columns = ["Fecha", "Order ID", "Cliente", "Cédula/RUC", "Placa",
                   "Producto", "Galones", "Subtotal", "IVA", "Total",
                   "Secuencial", "Clave de acceso", "Observación"]
        data_rows = []
        total_sum = 0.0
        for d in rows:
            detail = (await db.execute(
                select(DispatchDetail).where(DispatchDetail.dispatch_id == d.dispatch_id)
            )).scalars().first()
            product = None
            if detail:
                product = (await db.execute(
                    select(Product).where(Product.product_id == detail.product_id)
                )).scalar_one_or_none()
            person = persons.get(d.person_id)
            vehicle = vehicles.get(d.vehicle_id)
            fecha = d.created_at.astimezone(ECUADOR_TZ).strftime("%d/%m/%Y %H:%M") if d.created_at else ""
            total = float(d.total or 0)
            total_sum += total
            data_rows.append([
                fecha,
                d.order_id or "",
                person.name if person else "",
                person.id_number if person else "",
                vehicle.plate if vehicle else "",
                product.name if product else "",
                f"{float(detail.quantity):.2f}" if detail and detail.quantity else "",
                f"${float(d.subtotal or 0):,.2f}",
                f"${float(d.tax_amount or 0):,.2f}",
                f"${total:,.2f}",
                d.sequential_number or "",
                d.access_key or "",
                "Nunca enviada a Key49 — verificar con contabilidad",
            ])
        data_rows.append(["", "", "", "", "", "", "", "", "TOTAL", f"${total_sum:,.2f}", "", "", ""])

    xlsx = generate_excel("Ventas sin factura electrónica (revisión contable)", columns, data_rows)
    with open(out_path, "wb") as fh:
        fh.write(xlsx)
    print(f"{len(rows)} despachos → {out_path} (total ${total_sum:,.2f})")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "/home/pvalarezo/ventas_sin_facturar.xlsx"
    asyncio.run(main(path))
