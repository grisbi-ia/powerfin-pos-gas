"""Credit contracts — CRUD, available balance."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.database import get_db
from app.models.credit import CreditContract, CreditContractProduct, CreditContractVehicle
from app.models.person import Person, Vehicle
from app.models.product import Product
from app.models.user import User
from app.schemas import (
    CreateCreditContractRequest,
    CreditContractAvailableResponse,
    CreditContractProductResponse,
    CreditContractResponse,
    CreditContractVehicleResponse,
    UpdateCreditContractRequest,
)
from app.services.credit_service import calcular_cupo_disponible

router = APIRouter(prefix="/api/pos/credit-contracts", tags=["credit-contracts"])


@router.get("", response_model=list[CreditContractResponse])
async def list_contracts(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """List active credit contracts with their vehicles and products."""
    result = await db.execute(
        select(CreditContract)
        .where(CreditContract.is_active == True)
        .options(
            selectinload(CreditContract.vehicles),
            selectinload(CreditContract.products),
        )
    )
    contracts = result.scalars().all()

    response = []
    for c in contracts:
        person = (await db.execute(
            select(Person).where(Person.person_id == c.person_id)
        )).scalar_one_or_none()

        # Vehicles
        vehicles = []
        for cv in c.vehicles:
            v = (await db.execute(
                select(Vehicle).where(Vehicle.vehicle_id == cv.vehicle_id)
            )).scalar_one_or_none()
            vehicles.append(CreditContractVehicleResponse(
                contract_vehicle_id=cv.contract_vehicle_id,
                vehicle_id=cv.vehicle_id,
                plate=v.plate if v else "???",
                date_from=cv.date_from,
                date_to=cv.date_to,
                is_active=cv.is_active,
            ))

        # Products
        products = []
        for cp in c.products:
            p = (await db.execute(
                select(Product).where(Product.product_id == cp.product_id)
            )).scalar_one_or_none()
            products.append(CreditContractProductResponse(
                contract_product_id=cp.contract_product_id,
                product_id=cp.product_id,
                product_code=p.code if p else "???",
                product_name=p.name if p else "???",
                amount=cp.amount,
            ))

        available = await calcular_cupo_disponible(db, c)

        response.append(CreditContractResponse(
            contract_id=c.contract_id,
            contract_code=c.contract_code,
            person_id=c.person_id,
            person_name=person.name if person else "???",
            contract_date=c.contract_date,
            cupo=c.cupo,
            contract_type=c.contract_type,
            sercop_type=c.sercop_type,
            notes=c.notes,
            is_active=c.is_active,
            vehicles=vehicles,
            products=products,
            available=available,
        ))

    return response


@router.get("/{contract_id}", response_model=CreditContractResponse)
async def get_contract(
    contract_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get a single contract with its details."""
    result = await db.execute(
        select(CreditContract)
        .where(CreditContract.contract_id == contract_id)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato no encontrado")

    person = (await db.execute(
        select(Person).where(Person.person_id == contract.person_id)
    )).scalar_one_or_none()

    cv_result = await db.execute(
        select(CreditContractVehicle).where(
            CreditContractVehicle.contract_id == contract_id
        )
    )
    vehicles = []
    for cv in cv_result.scalars().all():
        v = (await db.execute(
            select(Vehicle).where(Vehicle.vehicle_id == cv.vehicle_id)
        )).scalar_one_or_none()
        vehicles.append(CreditContractVehicleResponse(
            contract_vehicle_id=cv.contract_vehicle_id,
            vehicle_id=cv.vehicle_id,
            plate=v.plate if v else "???",
            date_from=cv.date_from,
            date_to=cv.date_to,
            is_active=cv.is_active,
        ))

    cp_result = await db.execute(
        select(CreditContractProduct).where(
            CreditContractProduct.contract_id == contract_id
        )
    )
    products = []
    for cp in cp_result.scalars().all():
        p = (await db.execute(
            select(Product).where(Product.product_id == cp.product_id)
        )).scalar_one_or_none()
        products.append(CreditContractProductResponse(
            contract_product_id=cp.contract_product_id,
            product_id=cp.product_id,
            product_code=p.code if p else "???",
            product_name=p.name if p else "???",
            amount=cp.amount,
        ))

    available = await calcular_cupo_disponible(db, contract)

    return CreditContractResponse(
        contract_id=contract.contract_id,
        contract_code=contract.contract_code,
        person_id=contract.person_id,
        person_name=person.name if person else "???",
        contract_date=contract.contract_date,
        cupo=contract.cupo,
        contract_type=contract.contract_type,
        sercop_type=contract.sercop_type,
        notes=contract.notes,
        is_active=contract.is_active,
        vehicles=vehicles,
        products=products,
        available=available,
    )


@router.post("", response_model=CreditContractResponse, status_code=201)
async def create_contract(
    body: CreateCreditContractRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Create a new credit contract with vehicles and product amounts."""
    contract = CreditContract(
        contract_code=body.contract_code,
        person_id=body.person_id,
        contract_date=body.contract_date,
        cupo=body.cupo,
        contract_type=body.contract_type,
        sercop_type=body.sercop_type,
        notes=body.notes,
    )
    db.add(contract)
    await db.flush()

    for v in body.vehicles:
        cv = CreditContractVehicle(
            contract_id=contract.contract_id,
            vehicle_id=v.vehicle_id,
            date_from=v.date_from,
            date_to=v.date_to,
        )
        db.add(cv)

    for p in body.products:
        cp = CreditContractProduct(
            contract_id=contract.contract_id,
            product_id=p.product_id,
            amount=p.amount,
        )
        db.add(cp)

    await db.commit()

    person = (await db.execute(
        select(Person).where(Person.person_id == contract.person_id)
    )).scalar_one_or_none()

    return CreditContractResponse(
        contract_id=contract.contract_id,
        contract_code=contract.contract_code,
        person_id=contract.person_id,
        person_name=person.name if person else "???",
        contract_date=contract.contract_date,
        cupo=contract.cupo,
        contract_type=contract.contract_type,
        sercop_type=contract.sercop_type,
        notes=contract.notes,
        is_active=contract.is_active,
        vehicles=[],
        products=[],
    )


@router.put("/{contract_id}")
async def update_contract(
    contract_id: int,
    body: UpdateCreditContractRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Update a credit contract's fields."""
    result = await db.execute(
        select(CreditContract).where(CreditContract.contract_id == contract_id)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato no encontrado")

    if body.cupo is not None:
        contract.cupo = body.cupo
    if body.contract_type is not None:
        contract.contract_type = body.contract_type
    if body.sercop_type is not None:
        contract.sercop_type = body.sercop_type
    if body.notes is not None:
        contract.notes = body.notes
    if body.is_active is not None:
        contract.is_active = body.is_active

    await db.commit()
    return {"status": "ok"}


@router.get("/{contract_id}/available", response_model=CreditContractAvailableResponse)
async def get_contract_available(
    contract_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get real-time available credit for a contract."""
    result = await db.execute(
        select(CreditContract).where(CreditContract.contract_id == contract_id)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato no encontrado")

    available = await calcular_cupo_disponible(db, contract)
    consumed = contract.cupo - available

    return CreditContractAvailableResponse(
        contract_id=contract.contract_id,
        contract_code=contract.contract_code,
        cupo=contract.cupo,
        consumed=consumed,
        available=available,
        contract_type=contract.contract_type,
    )
