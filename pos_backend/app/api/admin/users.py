"""Admin users CRUD — list, create, read, update, soft-delete."""

import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.admin.deps import get_admin_user, require_permission
from app.database import get_db
from app.models.user import Role, User
from app.schemas import (
    AdminUserDetail,
    AdminUserListItem,
    CreateUserRequest,
    ErrorResponse,
    PaginatedResponse,
    UpdateUserRequest,
)
from app.services.auth_service import hash_pin

router = APIRouter(
    prefix="/api/admin/users",
    tags=["admin-users"],
    dependencies=[Depends(get_admin_user)],
)


# ── Helpers ────────────────────────────────────────────────────────


def _user_to_list_item(user: User) -> dict:
    return {
        "user_id": user.user_id,
        "username": user.username,
        "name": user.name,
        "role": user.role.code if user.role else "???",
        "role_name": user.role.name if user.role else "???",
        "is_active": user.is_active,
    }


def _user_to_detail(user: User) -> dict:
    return {
        "user_id": user.user_id,
        "username": user.username,
        "name": user.name,
        "role_id": user.role_id,
        "role": user.role.code if user.role else "???",
        "role_name": user.role.name if user.role else "???",
        "accounting_cash_code": user.accounting_cash_code,
        "is_active": user.is_active,
    }


# ── Endpoints ──────────────────────────────────────────────────────


@router.get("", response_model=PaginatedResponse)
async def list_users(
    search: str = Query("", description="Search by name, username, or role"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = Query("name", pattern=r"^(name|username|role|is_active)$"),
    order: str = Query("asc", pattern=r"^(asc|desc)$"),
    role: str = Query("", description="Filter by role code (ADMIN, DISPATCHER, etc.)"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("users", "read")),
):
    """List users with search, pagination, sorting, and role filter."""
    # Base query with role eager-loaded
    base = select(User).options(selectinload(User.role))

    # Count query (same filters, no pagination)
    count_q = select(func.count(User.user_id))

    # Apply filters
    if search:
        pattern = f"%{search.strip().lower()}%"
        filter_clause = or_(
            func.lower(User.name).like(pattern),
            func.lower(User.username).like(pattern),
        )
        base = base.where(filter_clause)
        count_q = count_q.where(filter_clause)

    if role:
        # Filter by role code via join
        base = base.join(User.role).where(Role.code == role.upper())
        count_q = count_q.join(User.role).where(Role.code == role.upper())

    # Count
    total = (await db.execute(count_q)).scalar() or 0
    pages = max(1, math.ceil(total / page_size))

    # Sort
    sort_col = getattr(User, sort, User.name)
    if order == "desc":
        sort_col = sort_col.desc()

    # Fetch page
    offset = (page - 1) * page_size
    result = await db.execute(base.order_by(sort_col).offset(offset).limit(page_size))
    users = result.scalars().all()

    return PaginatedResponse(
        items=[_user_to_list_item(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post(
    "",
    response_model=AdminUserDetail,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}},
)
async def create_user(
    body: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("users", "write")),
):
    """Create a new user. Username must be unique. Password is bcrypt-hashed."""
    # Check username uniqueness
    existing = await db.execute(
        select(User).where(User.username == body.username.lower())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El usuario '{body.username}' ya existe",
        )

    # Validate role exists
    role = await db.get(Role, body.role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rol con id {body.role_id} no encontrado",
        )

    user = User(
        username=body.username.lower(),
        name=body.name,
        pin_hash=hash_pin(body.password),
        role_id=body.role_id,
        accounting_cash_code=body.accounting_cash_code,
        is_active=body.is_active,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Eager-load role for response
    user = (await db.execute(
        select(User).where(User.user_id == user.user_id).options(selectinload(User.role))
    )).scalar_one()

    return _user_to_detail(user)


@router.get(
    "/{user_id}",
    response_model=AdminUserDetail,
    responses={404: {"model": ErrorResponse}},
)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("users", "read")),
):
    """Get a single user by id."""
    result = await db.execute(
        select(User).where(User.user_id == user_id).options(selectinload(User.role))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return _user_to_detail(user)


@router.put(
    "/{user_id}",
    response_model=AdminUserDetail,
    responses={404: {"model": ErrorResponse}},
)
async def update_user(
    user_id: int,
    body: UpdateUserRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("users", "write")),
):
    """Update user fields. Only provided fields are changed."""
    result = await db.execute(
        select(User).where(User.user_id == user_id).options(selectinload(User.role))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if body.name is not None:
        user.name = body.name
    if body.password is not None:
        user.pin_hash = hash_pin(body.password)
    if body.role_id is not None:
        role = await db.get(Role, body.role_id)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Rol con id {body.role_id} no encontrado",
            )
        user.role_id = body.role_id
        user.role = role  # update in-memory for response
    if body.accounting_cash_code is not None:
        user.accounting_cash_code = body.accounting_cash_code
    if body.is_active is not None:
        user.is_active = body.is_active

    await db.commit()
    await db.refresh(user)
    return _user_to_detail(user)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("users", "delete")),
):
    """Soft-delete a user (sets is_active=False)."""
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user.is_active = False
    await db.commit()
