"""Vehicle lookup endpoint."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.database import get_db
from app.models import Person, Vehicle
from app.models.pricing import PriceList
from app.models.user import User
from app.schemas import VehicleOwner, VehicleResponse, SetBillingPersonRequest

router = APIRouter(prefix="/api/pos", tags=["vehicles"])


@router.get("/vehicles", response_model=VehicleResponse)
async def lookup_vehicle(
    plate: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Look up a vehicle by license plate. Returns owner and price list info."""
    cleaned = plate.upper().replace(" ", "").replace("-", "")

    result = await db.execute(
        select(Vehicle)
        .where(Vehicle.plate == cleaned, Vehicle.is_active == True)
        .options(selectinload(Vehicle.person), selectinload(Vehicle.billing_person))
    )
    vehicle = result.scalar_one_or_none()

    if not vehicle:
        return VehicleResponse(
            vehicle_id=0,
            plate=cleaned,
            vehicle_found=False,
            price_list="STANDARD",
            price_list_name="Precio Normal",
        )

    # Get person
    person_result = await db.execute(
        select(Person).where(Person.person_id == vehicle.person_id)
    )
    person = person_result.scalar_one_or_none()

    # Determine price list
    price_list_code = "STANDARD"
    price_list_name = "Precio Normal"

    # Priority: vehicle.price_list > person.price_list > default
    pl_id = vehicle.price_list_id or (person.price_list_id if person else None)
    if pl_id:
        pl_result = await db.execute(
            select(PriceList).where(PriceList.price_list_id == pl_id)
        )
        pl = pl_result.scalar_one_or_none()
        if pl:
            price_list_code = pl.code
            price_list_name = pl.name

    # Check incomplete fields
    incomplete = []
    if person:
        if not person.email:
            incomplete.append("email")
        if not person.phone:
            incomplete.append("phone")
        if not person.address:
            incomplete.append("address")

    owner = None
    if person:
        owner = VehicleOwner(
            person_id=person.person_id,
            customer_id=person.id_number,
            id_type=person.id_type,
            id_number=person.id_number,
            name=person.name,
            address=person.address,
            email=person.email,
            phone=person.phone,
        )

    # Build billing_person when set (different from owner)
    billing_person = None
    if vehicle.billing_person_id and vehicle.billing_person:
        bp = vehicle.billing_person
        billing_person = VehicleOwner(
            person_id=bp.person_id,
            customer_id=bp.id_number,
            id_type=bp.id_type,
            id_number=bp.id_number,
            name=bp.name,
            address=bp.address,
            email=bp.email,
            phone=bp.phone,
        )

    return VehicleResponse(
        vehicle_id=vehicle.vehicle_id,
        plate=cleaned,
        vehicle_found=True,
        incomplete_fields=incomplete,
        owner=owner,
        billing_person=billing_person,
        price_list=price_list_code,
        price_list_name=price_list_name,
    )


@router.put("/vehicles/{vehicle_id}/billing-person")
async def set_billing_person(
    vehicle_id: int,
    body: SetBillingPersonRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Set or clear the preferred billing person for a vehicle.

    - person_id = None → clear, use owner (person_id) for billing
    - person_id = <id> → always bill to this person
    """
    result = await db.execute(
        select(Vehicle).where(Vehicle.vehicle_id == vehicle_id)
    )
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")

    if body.person_id is not None:
        # Verify person exists
        p = await db.execute(
            select(Person).where(Person.person_id == body.person_id)
        )
        if not p.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Persona no encontrada")

    vehicle.billing_person_id = body.person_id
    await db.commit()

    return {"status": "ok", "billing_person_id": body.person_id}
