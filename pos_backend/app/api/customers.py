"""Customer endpoints — search, lookup, create."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models import Person, Vehicle
from app.models.pricing import PriceList
from app.models.user import User
from app.schemas import (
    CreateCustomerRequest,
    CreateCustomerResponse,
    CustomerResponse,
)

router = APIRouter(prefix="/api/pos/customers", tags=["customers"])


@router.get("", response_model=list[CustomerResponse])
async def search_customers(
    q: str = Query(""),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Search customers by name, ID number, or plate."""
    query = q.lower().strip()
    if not query:
        return []

    # Search persons by name or id_number
    result = await db.execute(
        select(Person)
        .where(
            Person.is_active == True,
            or_(
                Person.name.ilike(f"%{query}%"),
                Person.id_number.ilike(f"%{query}%"),
            ),
        )
        .limit(20)
    )
    persons = result.scalars().all()

    # Also search by plate
    vehicle_result = await db.execute(
        select(Vehicle).where(
            Vehicle.is_active == True,
            Vehicle.plate.ilike(f"%{query}%"),
        )
    )
    vehicles = vehicle_result.scalars().all()
    person_ids_from_vehicles = {v.person_id for v in vehicles}
    if person_ids_from_vehicles:
        extra = await db.execute(
            select(Person).where(
                Person.person_id.in_(person_ids_from_vehicles),
                Person.person_id.notin_([p.person_id for p in persons]),
            )
        )
        persons.extend(extra.scalars().all())

    # Build response
    response = []
    for person in persons:
        # Get plates
        person_vehicles = await db.execute(
            select(Vehicle).where(Vehicle.person_id == person.person_id)
        )
        plates = [v.plate for v in person_vehicles.scalars().all()]

        # Get price list
        pl_code = "STANDARD"
        pl_name = "Precio Normal"
        if person.price_list_id:
            pl = (await db.execute(
                select(PriceList).where(PriceList.price_list_id == person.price_list_id)
            )).scalar_one_or_none()
            if pl:
                pl_code = pl.code
                pl_name = pl.name

        response.append(
            CustomerResponse(
                customer_id=person.id_number,
                id_type=person.id_type,
                id_number=person.id_number,
                name=person.name,
                email=person.email,
                phone=person.phone,
                price_list=pl_code,
                price_list_name=pl_name,
                credit_active=False,
                credit_balance=0,
                plates=plates,
            )
        )

    return response


@router.get("/by-id", response_model=CustomerResponse)
async def get_customer_by_id(
    id_type: str = Query(...),
    id_number: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Look up a customer by identification type and number."""
    result = await db.execute(
        select(Person).where(
            Person.id_type == id_type,
            Person.id_number == id_number,
            Person.is_active == True,
        )
    )
    person = result.scalar_one_or_none()

    if not person:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    # Plates
    vehicle_result = await db.execute(
        select(Vehicle).where(Vehicle.person_id == person.person_id)
    )
    plates = [v.plate for v in vehicle_result.scalars().all()]

    # Price list
    pl_code = "STANDARD"
    pl_name = "Precio Normal"
    if person.price_list_id:
        pl = (await db.execute(
            select(PriceList).where(PriceList.price_list_id == person.price_list_id)
        )).scalar_one_or_none()
        if pl:
            pl_code = pl.code
            pl_name = pl.name

    return CustomerResponse(
        customer_id=person.id_number,
        id_type=person.id_type,
        id_number=person.id_number,
        name=person.name,
        email=person.email,
        phone=person.phone,
        price_list=pl_code,
        price_list_name=pl_name,
        credit_active=False,
        credit_balance=0,
        plates=plates,
    )


@router.post("", response_model=CreateCustomerResponse, status_code=201)
async def create_customer(
    body: CreateCustomerRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Register a new customer and optionally link a vehicle plate."""
    # Check if already exists
    existing = (await db.execute(
        select(Person).where(
            Person.id_type == body.id_type, Person.id_number == body.id_number
        )
    )).scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=409, detail="El cliente ya existe")

    person = Person(
        id_type=body.id_type,
        id_number=body.id_number,
        name=body.name,
        email=body.email,
    )
    db.add(person)
    await db.flush()

    # Create vehicle if plate provided
    if body.plate:
        cleaned = body.plate.upper().replace(" ", "").replace("-", "")
        existing_vehicle = (await db.execute(
            select(Vehicle).where(Vehicle.plate == cleaned)
        )).scalar_one_or_none()
        if not existing_vehicle:
            v = Vehicle(plate=cleaned, person_id=person.person_id)
            db.add(v)

    await db.commit()

    return CreateCustomerResponse(
        customer_id=person.id_number,
        price_list="STANDARD",
    )
