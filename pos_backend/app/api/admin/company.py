"""Admin company info — GET/PUT the single-row company configuration."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.deps import get_admin_user, require_permission
from app.database import get_db
from app.models.company import CompanyInfo
from app.models.user import User
from app.schemas import AdminCompanyInfoResponse, ErrorResponse, UpdateCompanyInfoRequest

router = APIRouter(
    prefix="/api/admin/company-info",
    tags=["admin-company-info"],
    dependencies=[Depends(get_admin_user)],
)


def _company_to_dict(c: CompanyInfo) -> dict:
    return {
        "company_id": c.company_id,
        "ruc": c.ruc,
        "name": c.name,
        "commercial_name": c.commercial_name,
        "address": c.address,
        "phone": c.phone,
        "email": c.email,
        "city": c.city,
        "province": c.province,
        "country": c.country,
        "fiscal_regime": c.fiscal_regime,
        "sri_environment": c.sri_environment,
        "emission_type": c.emission_type,
        "logo_url": c.logo_url,
        "is_active": c.is_active,
    }


@router.get("", response_model=AdminCompanyInfoResponse)
async def get_company_info(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("company_info", "read")),
):
    """Get the single company info record."""
    result = await db.execute(select(CompanyInfo).limit(1))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Información de empresa no configurada")
    return _company_to_dict(c)


@router.put(
    "",
    response_model=AdminCompanyInfoResponse,
    responses={404: {"model": ErrorResponse}},
)
async def update_company_info(
    body: UpdateCompanyInfoRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("company_info", "write")),
):
    """Update company info fields. Only provided fields are changed."""
    result = await db.execute(select(CompanyInfo).limit(1))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Información de empresa no configurada")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(c, key):
            setattr(c, key, value)

    await db.commit()
    await db.refresh(c)
    return _company_to_dict(c)
