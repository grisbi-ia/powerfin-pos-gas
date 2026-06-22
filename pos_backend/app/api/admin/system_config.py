"""Admin system config — GET all keys, PUT per key.

System config is a key-value store for runtime settings (printer_policy,
max_cash_in_hand, key49_api_key, etc.).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.deps import get_admin_user, require_permission
from app.database import get_db
from app.models.company import SystemConfig
from app.models.user import User
from app.schemas import AdminSystemConfigItem, ErrorResponse, UpdateSystemConfigRequest

router = APIRouter(
    prefix="/api/admin/system-config",
    tags=["admin-system-config"],
    dependencies=[Depends(get_admin_user)],
)


def _config_to_dict(sc: SystemConfig) -> dict:
    return {
        "key": sc.key,
        "value": sc.value,
        "description": sc.description,
        "updated_at": sc.updated_at,
    }


@router.get("", response_model=list[AdminSystemConfigItem])
async def list_system_config(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("system_config", "read")),
):
    """List all system config entries (key-value pairs)."""
    result = await db.execute(select(SystemConfig).order_by(SystemConfig.key))
    configs = result.scalars().all()
    return [_config_to_dict(c) for c in configs]


@router.put(
    "/{key:path}",
    response_model=AdminSystemConfigItem,
    responses={404: {"model": ErrorResponse}},
)
async def update_system_config(
    key: str,
    body: UpdateSystemConfigRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("system_config", "write")),
):
    """Update a system config value. Creates the key if it doesn't exist.

    The `{key:path}` pattern allows keys with slashes (e.g., "api/sri/url").
    """
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == key)
    )
    sc = result.scalar_one_or_none()

    if not sc:
        sc = SystemConfig(key=key, value=body.value, description=body.description)
        db.add(sc)
    else:
        sc.value = body.value
        if body.description is not None:
            sc.description = body.description

    await db.commit()
    await db.refresh(sc)
    return _config_to_dict(sc)
