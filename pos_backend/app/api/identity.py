"""Identity lookup endpoint — auto-fill person data from Sercobaco/SRI."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_current_user
from app.models.user import User
from app.services.identity_service import IdentityLookupError, lookup_person

router = APIRouter(prefix="/api/pos/identity", tags=["identity"])


@router.get("/lookup")
async def identity_lookup(
    id_type: str = Query(..., description="CED or RUC"),
    id_number: str = Query(..., description="Identification number"),
    _user: User = Depends(get_current_user),
):
    """
    Look up a person's data from external identity APIs.

    - CED → Sercobaco (name, address from civil registry)
    - RUC → SRI (company name, address from tax registry)

    Returns the person's name, address, and ID info.
    """
    try:
        person = await lookup_person(id_type.upper(), id_number)
    except IdentityLookupError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return {
        "found": True,
        "data": person.to_dict(),
    }
