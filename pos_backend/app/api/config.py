"""Config endpoint — full station configuration."""

from fastapi import APIRouter, Depends, HTTPException
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
from app.models.pricing import PriceListItem
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
    StationInfoResponse,
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
        ruc=company.ruc if company else None,
        address=company.address if company else None,
        phone=company.phone if company else None,
        city=company.city if company else None,
        province=company.province if company else None,
        country=company.country if company else None,
        fiscal_regime=company.fiscal_regime if company else None,
        sri_environment=company.sri_environment if company else None,
        emission_type=company.emission_type if company else None,
    )

    # Dispensers with hoses
    result = await db.execute(
        select(Dispenser)
        .where(Dispenser.is_active == True)
        .order_by(Dispenser.sort_order, Dispenser.dispenser_id)
        .options(selectinload(Dispenser.hoses))
    )
    dispensers_raw = result.scalars().all()

    # Product lookup for grade names and default prices
    products = (await db.execute(select(Product))).scalars().all()
    product_map = {p.code: p.name for p in products}
    
    # Default price list items (STANDARD prices for each product)
    from app.models.pricing import PriceListItem
    default_pl = (await db.execute(
        select(PriceList).where(PriceList.is_default == True)
    )).scalar_one_or_none()
    default_prices = {}
    if default_pl:
        pl_items = (await db.execute(
            select(PriceListItem).where(PriceListItem.price_list_id == default_pl.price_list_id)
        )).scalars().all()
        for item in pl_items:
            # Map product_id → unit_price
            for p in products:
                if p.product_id == item.product_id:
                    default_prices[p.code] = float(item.unit_price)
    
    # Map grade code → product code
    grades_result = (await db.execute(select(Grade))).scalars().all()
    grade_product_map = {}
    for g in grades_result:
        for p in products:
            if p.product_id == g.product_id:
                grade_product_map[g.code] = p.code
    
    # Also collect grades list
    grades = [
        GradeResponse(
            grade_id=g.code,
            name=g.name,
            unit="GAL",
        )
        for g in grades_result
    ]

    # Product info for base_price and subsidy
    product_info = {}
    for p in products:
        product_info[p.code] = {
            "base_price": float(p.base_price) if p.base_price else 0,
            "subsidy_per_unit": float(p.subsidy_per_unit) if p.subsidy_per_unit else 0,
        }

    dispensers = []
    for d in dispensers_raw:
        sides: dict[str, list] = {"A": [], "B": []}
        for h in d.hoses:
            product_code = grade_product_map.get(h.grade_id, h.grade_id)
            pinfo = product_info.get(product_code, {})
            hose_data = HoseResponse(
                hose_id=h.hose_id,
                fusion_pump_id=h.fusion_pump_id,
                fusion_hose_id=h.fusion_hose_id,
                grade_id=h.grade_id,
                grade_name=product_map.get(h.grade_id, h.grade_id),
                unit_price=default_prices.get(product_code, 0),
                base_price=pinfo.get("base_price", 0),
                subsidy_per_unit=pinfo.get("subsidy_per_unit", 0),
            )
            sides[h.side].append(hose_data)
        dispensers.append(
            DispenserConfigResponse(
                dispenser_id=d.dispenser_id,
                name=d.name,
                printer_ip=d.printer_ip,
                printer_port=d.printer_port,
                sides={k: v for k, v in sides.items() if v},
            )
        )

    # Price lists
    pl_result = (await db.execute(select(PriceList))).scalars().all()
    price_lists = [PriceListResponse(code=pl.code, name=pl.name) for pl in pl_result]

    # Payment methods
    pm_result = (
        await db.execute(select(PaymentMethod).where(PaymentMethod.is_active == True))
    ).scalars().all()
    payment_methods = [
        PaymentMethodResponse(
            code=pm.code, name=pm.name, requires_reference=pm.requires_reference,
            sri_code=pm.sri_code
        )
        for pm in pm_result
    ]

    # Polling config
    polling = PollingConfig(interval_ms=2000, enabled=True)

    # Printer policy from system_config or default
    printer_policy = "ASK"
    policy_cfg = (await db.execute(
        select(SystemConfig).where(SystemConfig.key == "printer_policy")
    )).scalar_one_or_none()
    if policy_cfg:
        printer_policy = policy_cfg.value

    max_cash_in_hand = 300.0
    max_cfg = (await db.execute(
        select(SystemConfig).where(SystemConfig.key == "max_cash_in_hand")
    )).scalar_one_or_none()
    if max_cfg:
        try: max_cash_in_hand = float(max_cfg.value)
        except (ValueError, TypeError): pass

    # Cash printer IP (separate from dispenser printers)
    cash_printer_ip = ""
    cash_printer_port = 9100
    cp_ip = (await db.execute(
        select(SystemConfig).where(SystemConfig.key == "cash_printer_ip")
    )).scalar_one_or_none()
    if cp_ip and cp_ip.value:
        cash_printer_ip = cp_ip.value
    cp_port = (await db.execute(
        select(SystemConfig).where(SystemConfig.key == "cash_printer_port")
    )).scalar_one_or_none()
    if cp_port and cp_port.value:
        try: cash_printer_port = int(cp_port.value)
        except (ValueError, TypeError): pass

    return ConfigResponse(
        location=location,
        dispensers=dispensers,
        grades=grades,
        price_lists=price_lists,
        payment_methods=payment_methods,
        printer_policy=printer_policy,
        max_cash_in_hand=max_cash_in_hand,
        cash_printer_ip=cash_printer_ip,
        cash_printer_port=cash_printer_port,
        polling=polling,
    )


@router.get("/station-info", response_model=StationInfoResponse)
async def get_station_info(
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint — returns station name for the login page."""
    company = (await db.execute(select(CompanyInfo).limit(1))).scalar_one_or_none()
    if company:
        return StationInfoResponse(
            name=company.name or "Powerfin GAS",
            commercial_name=company.commercial_name,
        )
    return StationInfoResponse(name="Powerfin GAS")
