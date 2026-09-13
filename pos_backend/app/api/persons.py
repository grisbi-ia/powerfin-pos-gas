"""Unified person lookup — local DB first, then external identity API."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models import Person, Vehicle
from app.models.user import User
from app.schemas import UpdatePersonRequest
from app.services.id_validation import normalize_id_number, validate_identification
from app.services.identity_service import (
    IdentityLookupError,
    IdentityNotFoundError,
    lookup_person,
)

router = APIRouter(prefix="/api/pos/persons", tags=["persons"])


@router.get("/lookup")
async def person_lookup(
    id_type: str = Query(..., description="CED or RUC"),
    id_number: str = Query(..., description="Identification number"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    Unified person lookup with fallback chain:

    0. Validate the identification (cédula module-10 / RUC structure). An
       invalid number never reaches the DB nor the external API: it comes
       back as 422 so the dispatcher asks the customer again.
    1. Search local PostgreSQL → if found, return immediately
    2. Call external identity API (Sercobaco/SRI) with 5s timeout
    3. If external API returns data, return it (marked as local: false)
    4. If nothing found, return found: false → POS shows manual form
    """
    id_type = id_type.upper()
    id_number = normalize_id_number(id_number)

    # ═══════════════════════════════════════════════
    # Step 0: local validation of the identification
    # ═══════════════════════════════════════════════
    error = validate_identification(id_type, id_number)
    if error:
        raise HTTPException(status_code=422, detail=error)

    # ═══════════════════════════════════════════════
    # Step 1: Search local database
    # ═══════════════════════════════════════════════
    result = await db.execute(
        select(Person).where(
            Person.id_type == id_type,
            Person.id_number == id_number,
            Person.is_active == True,
        )
    )
    person = result.scalar_one_or_none()

    if person:
        # Get plates
        plates_result = await db.execute(
            select(Vehicle).where(Vehicle.person_id == person.person_id)
        )
        plates = [v.plate for v in plates_result.scalars().all()]

        # Get price list name
        from app.models.pricing import PriceList
        pl_code = "STANDARD"
        pl_name = "Precio Normal"
        if person.price_list_id:
            pl = (await db.execute(
                select(PriceList).where(PriceList.price_list_id == person.price_list_id)
            )).scalar_one_or_none()
            if pl:
                pl_code = pl.code
                pl_name = pl.name

        return {
            "found": True,
            "local": True,
            "source": "database",
            "data": {
                "person_id": person.person_id,
                "name": person.name,
                "id_type": person.id_type,
                "id_number": person.id_number,
                "address": person.address,
                "email": person.email,
                "phone": person.phone,
                "plates": plates,
                "price_list": pl_code,
                "price_list_name": pl_name,
            },
        }

    # ═══════════════════════════════════════════════
    # Step 2: Try external identity API
    # ═══════════════════════════════════════════════
    try:
        external = await lookup_person(id_type, id_number)
    except IdentityNotFoundError as e:
        # The registry answered: the number does not exist. Key49 would reject the
        # invoice, so the dispatcher must ask the customer again (blocked).
        raise HTTPException(
            status_code=422,
            detail=(
                f"{e}. Verifique el número con el cliente: no se puede "
                "facturar con una identificación inexistente."
            ),
        ) from e
    except IdentityLookupError:
        # Step 3: Nothing found anywhere. The identification itself is valid
        # (step 0), so the POS may register it manually — but the failed
        # verification is reported, never swallowed.
        return {
            "found": False,
            "local": False,
            "source": None,
            "data": None,
            "external_lookup_failed": True,
            "warning": (
                "No se pudo verificar automáticamente (Sercobaco/SRI). "
                "Confirme el nombre y los datos con el cliente."
            ),
        }

    # ═══════════════════════════════════════════════
    # Step 2.5: Auto-save external result locally
    # Avoids future API calls for the same person.
    # Uses INSERT … ON CONFLICT DO NOTHING to prevent
    # duplicates from concurrent requests.
    # ═══════════════════════════════════════════════
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    stmt = pg_insert(Person).values(
        id_type=external.id_type,
        id_number=external.id_number,
        name=external.name,
        address=external.address,
        email=external.email,
        phone=external.phone,
        is_active=True,
        price_list_id=None,
    ).on_conflict_do_nothing(
        constraint="persons_id_type_id_number_key"
    )
    await db.execute(stmt)
    await db.commit()

    # Re-fetch to get the person_id (may have been inserted by concurrent request)
    saved = await db.execute(
        select(Person).where(
            Person.id_type == id_type,
            Person.id_number == id_number,
        )
    )
    saved_person_id = saved.scalar_one().person_id if saved else None

    return {
        "found": True,
        "local": True,
        "source": "identity_api",
        "data": {
            "person_id": saved_person_id,
            "name": external.name,
            "id_type": external.id_type,
            "id_number": external.id_number,
            "address": external.address,
            "email": external.email,
            "phone": external.phone,
            "plates": [],
            "price_list": "STANDARD",
            "price_list_name": "Precio Normal",
        },
    }


@router.put("/{person_id}")
async def update_person(
    person_id: int,
    body: UpdatePersonRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Update a person's fields (name, address, phone, email, etc.).

    Also the endpoint the POS uses to **re-capture an identification** after the
    dispatcher asked the customer again (used to fix customers whose recorded
    identification was invalid/cleared). Sending `id_number` requires
    `id_type` and validates the check digit — an invalid number is refused with
    422, never stored.
    """
    result = await db.execute(
        select(Person).where(Person.person_id == person_id)
    )
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="Persona no encontrada")

    # ── Identification change (re-capture) ──
    if body.id_number is not None:
        new_number = normalize_id_number(body.id_number)
        new_type = (body.id_type or person.id_type or "").strip().upper()

        error = validate_identification(new_type, new_number)
        if error:
            raise HTTPException(status_code=422, detail=error)

        # The unique constraint is (id_type, id_number) — check explicitly so
        # the dispatcher gets a clear message instead of an IntegrityError.
        duplicate = (await db.execute(
            select(Person).where(
                Person.id_type == new_type,
                Person.id_number == new_number,
                Person.person_id != person_id,
            )
        )).scalar_one_or_none()
        if duplicate:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"La identificación {new_number} ya está registrada "
                    f"a nombre de {duplicate.name}."
                ),
            )

        person.id_type = new_type
        person.id_number = new_number

    if body.name is not None:
        person.name = body.name
    if body.address is not None:
        person.address = body.address
    if body.phone is not None:
        person.phone = body.phone
    if body.email is not None:
        person.email = body.email
    if body.price_list_id is not None:
        person.price_list_id = body.price_list_id
    if body.yalobox_wallet is not None:
        person.yalobox_wallet = body.yalobox_wallet

    await db.commit()
    return {
        "status": "ok",
        "person_id": person.person_id,
        "id_type": person.id_type,
        "id_number": person.id_number,
    }
