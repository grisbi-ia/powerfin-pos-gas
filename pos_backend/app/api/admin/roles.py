"""Admin roles CRUD — list, create, read, update.

Roles are NOT soft-deletable because they are FK'd from users.
Only deactivation (is_active=False) is supported through the update endpoint.
"""

import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.deps import get_admin_user, require_permission
from app.database import get_db
from app.models.user import Role, User
from app.schemas import (
    AdminRoleDetail,
    AdminRoleListItem,
    CreateRoleRequest,
    ErrorResponse,
    PaginatedResponse,
    UpdateRoleRequest,
)

router = APIRouter(
    prefix="/api/admin/roles",
    tags=["admin-roles"],
    dependencies=[Depends(get_admin_user)],
)


# ── Helpers ────────────────────────────────────────────────────────


def _role_to_list_item(role: Role) -> dict:
    return {
        "role_id": role.role_id,
        "code": role.code,
        "name": role.name,
        "is_active": role.is_active,
    }


def _role_to_detail(role: Role) -> dict:
    return {
        "role_id": role.role_id,
        "code": role.code,
        "name": role.name,
        "permissions_json": role.permissions_json,
        "is_active": role.is_active,
    }


# ── Endpoints ──────────────────────────────────────────────────────


@router.get("", response_model=PaginatedResponse)
async def list_roles(
    search: str = Query("", description="Search by name or code"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = Query("name", pattern=r"^(name|code|is_active)$"),
    order: str = Query("asc", pattern=r"^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("roles", "read")),
):
    """List roles with search, pagination, and sorting."""
    base = select(Role)
    count_q = select(func.count(Role.role_id))

    if search:
        pattern = f"%{search.strip().lower()}%"
        from sqlalchemy import or_
        filter_clause = or_(
            func.lower(Role.name).like(pattern),
            func.lower(Role.code).like(pattern),
        )
        base = base.where(filter_clause)
        count_q = count_q.where(filter_clause)

    # Count
    total = (await db.execute(count_q)).scalar() or 0
    pages = max(1, math.ceil(total / page_size))

    # Sort
    sort_col = getattr(Role, sort, Role.name)
    if order == "desc":
        sort_col = sort_col.desc()

    # Fetch page
    offset = (page - 1) * page_size
    result = await db.execute(base.order_by(sort_col).offset(offset).limit(page_size))
    roles = result.scalars().all()

    return PaginatedResponse(
        items=[_role_to_list_item(r) for r in roles],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post(
    "",
    response_model=AdminRoleDetail,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}},
)
async def create_role(
    body: CreateRoleRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("roles", "write")),
):
    """Create a new role. Code must be unique."""
    # Check code uniqueness
    existing = await db.execute(
        select(Role).where(Role.code == body.code.upper())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El rol con código '{body.code}' ya existe",
        )

    role = Role(
        code=body.code.upper(),
        name=body.name,
        permissions_json=body.permissions_json,
        is_active=body.is_active,
    )
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return _role_to_detail(role)


@router.get(
    "/{role_id}",
    response_model=AdminRoleDetail,
    responses={404: {"model": ErrorResponse}},
)
async def get_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("roles", "read")),
):
    """Get a single role by id."""
    role = await db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    return _role_to_detail(role)


@router.put(
    "/{role_id}",
    response_model=AdminRoleDetail,
    responses={404: {"model": ErrorResponse}},
)
async def update_role(
    role_id: int,
    body: UpdateRoleRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("roles", "write")),
):
    """Update role fields. Only provided fields are changed.

    The role code cannot be changed (it's the stable identifier).
    Use is_active=False to deactivate a role.
    """
    role = await db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Rol no encontrado")

    if body.name is not None:
        role.name = body.name
    if body.permissions_json is not None:
        role.permissions_json = body.permissions_json
    if body.is_active is not None:
        role.is_active = body.is_active

    await db.commit()
    await db.refresh(role)
    return _role_to_detail(role)
