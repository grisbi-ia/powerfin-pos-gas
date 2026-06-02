"""Price lookup endpoint."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models import Grade, Person, PriceList, PriceListItem, Product, Vehicle
from app.models.user import User
from app.schemas import PriceResponse

router = APIRouter(prefix="/api/pos", tags=["prices"])


@router.get("/prices", response_model=PriceResponse)
async def get_prices(
    vehicleId: str = Query(None),
    customerId: str = Query(None),
    gradeId: str = Query("DIESEL"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    Get the price for a grade given a vehicle or customer.
    Priority: vehicle.price_list > person.price_list > default STANDARD.
    """
    price_list_code = "STANDARD"
    price_list_name = "Precio Normal"
    price_list_id = None

    # Try vehicle first (highest priority)
    if vehicleId:
        cleaned = vehicleId.upper().replace(" ", "").replace("-", "")
        v_result = await db.execute(
            select(Vehicle).where(Vehicle.plate == cleaned, Vehicle.is_active == True)
        )
        vehicle = v_result.scalar_one_or_none()
        if vehicle:
            pl_id = vehicle.price_list_id
            if not pl_id:
                # Fallback to person's price list
                p_result = await db.execute(
                    select(Person).where(Person.person_id == vehicle.person_id)
                )
                person = p_result.scalar_one_or_none()
                if person and person.price_list_id:
                    pl_id = person.price_list_id
            if pl_id:
                price_list_id = pl_id

    # Try customerId
    elif customerId:
        p_result = await db.execute(
            select(Person).where(
                Person.id_number == customerId, Person.is_active == True
            )
        )
        person = p_result.scalar_one_or_none()
        if person and person.price_list_id:
            price_list_id = person.price_list_id

    if price_list_id:
        pl_result = await db.execute(
            select(PriceList).where(PriceList.price_list_id == price_list_id)
        )
        pl = pl_result.scalar_one_or_none()
        if pl:
            price_list_code = pl.code
            price_list_name = pl.name

    # Find grade and product
    grade_result = await db.execute(
        select(Grade).where(Grade.code == gradeId)
    )
    grade = grade_result.scalar_one_or_none()
    if not grade:
        raise HTTPException(status_code=404, detail=f"Grade {gradeId} not found")

    # Get price from price_list_items or base_price
    unit_price = Decimal("0")
    if price_list_id:
        pli_result = await db.execute(
            select(PriceListItem).where(
                PriceListItem.price_list_id == price_list_id,
                PriceListItem.product_id == grade.product_id,
            )
        )
        pli = pli_result.scalar_one_or_none()
        if pli:
            unit_price = Decimal(str(pli.unit_price))

    if unit_price == Decimal("0"):
        # Fallback to product base price
        prod = (await db.execute(
            select(Product).where(Product.product_id == grade.product_id)
        )).scalar_one_or_none()
        if prod:
            unit_price = Decimal(str(prod.base_price))

    return PriceResponse(
        grade_id=grade.code,
        grade_name=grade.name,
        unit_price=unit_price,
        price_list=price_list_code,
        currency="USD",
    )
