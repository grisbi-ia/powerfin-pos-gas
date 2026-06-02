"""Config endpoint — full station configuration."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.database import get_db
from app.models import (
    CompanyInfo,
    Dispenser,
    Grade,
    Hose,
    PaymentMethod,
    PriceList,
    SystemConfig,
)
from app.models.product import Product
from app.models.user import User
from app.schemas import (
    ConfigResponse,
    DispenserConfigResponse,
    GradeResponse,
    HoseResponse,
    LocationResponse,
    PaymentMethodResponse,
    PollingConfig,
    PriceListResponse,
)

router = APIRouter(prefix="/api/pos", tags=["config"])


@router.get("/config", response_model=ConfigResponse)
async def get_config(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Return full station configuration: location, dispensers, grades, prices, payment methods."""

    # Company info
    company = (await db.execute(select(CompanyInfo).limit(1))).scalar_one_or_none()
    location = LocationResponse(
        location_id=company.company_id if company else 1,
        name=company.commercial_name or "NEOGAS" if company else "NEOGAS",
        address=company.address if company else None,
    )

    # Dispensers with hoses
    result = await db.execute(
        select(Dispenser)
        .where(Dispenser.is_active == True)
        .options(selectinload(Dispenser.hoses))
    )
    dispensers_raw = result.scalars().all()

    # Product lookup for grade names
    products = (await db.execute(select(Product))).scalars().all()
    product_map = {p.code: p.name for p in products}

    dispensers = []
    for d in dispensers_raw:
        sides: dict[str, list] = {"A": [], "B": []}
        for h in d.hoses:
            hose_data = HoseResponse(
                hose_id=h.hose_id,
                fusion_pump_id=h.fusion_pump_id,
                fusion_hose_id=h.fusion_hose_id,
                grade_id=h.grade_id,
                grade_name=product_map.get(h.grade_id, h.grade_id),
            )
            sides[h.side].append(hose_data)
        dispensers.append(
            DispenserConfigResponse(
                dispenser_id=d.dispenser_id,
                fusion_pump_id=d.fusion_pump_id,
                name=d.name,
                printer_island=1,
                sides={k: v for k, v in sides.items() if v},
            )
        )

    # Grades
    grades_result = (await db.execute(select(Grade))).scalars().all()
    grades = [
        GradeResponse(
            grade_id=g.code,
            name=g.name,
            unit="GAL",
        )
        for g in grades_result
    ]

    # Price lists
    pl_result = (await db.execute(select(PriceList))).scalars().all()
    price_lists = [PriceListResponse(code=pl.code, name=pl.name) for pl in pl_result]

    # Payment methods
    pm_result = (
        await db.execute(select(PaymentMethod).where(PaymentMethod.is_active == True))
    ).scalars().all()
    payment_methods = [
        PaymentMethodResponse(
            code=pm.code, name=pm.name, requires_reference=pm.requires_reference
        )
        for pm in pm_result
    ]

    # Polling config
    polling = PollingConfig(interval_ms=2000, enabled=True)

    return ConfigResponse(
        location=location,
        dispensers=dispensers,
        grades=grades,
        price_lists=price_lists,
        payment_methods=payment_methods,
        polling=polling,
    )
