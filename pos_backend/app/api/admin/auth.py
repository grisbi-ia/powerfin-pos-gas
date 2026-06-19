"""Admin auth endpoints — login for ADMIN/SUPERVISOR roles."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import AdminLoginRequest, AdminLoginResponse, ErrorResponse
from app.services.auth_service import authenticate_user, create_access_token

router = APIRouter(prefix="/api/admin/auth", tags=["admin-auth"])


@router.post(
    "/login",
    response_model=AdminLoginResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def admin_login(body: AdminLoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate an admin/supervisor user with username and password.

    Unlike the POS login (which uses a numeric PIN), this endpoint accepts
    a full-text password validated against the same bcrypt hash.

    Only users with role ADMIN or SUPERVISOR can authenticate here.
    DISPATCHER users receive a 403.
    """
    # Reuses the same authenticate_user from POS — bcrypt treats PIN and
    # password identically. No code duplication.
    user = await authenticate_user(db, body.username, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
        )

    # Role gate — dispatchers cannot log into the admin panel
    if not user.role or user.role.code == "DISPATCHER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso restringido — solo ADMIN y SUPERVISOR",
        )

    # Shorter JWT for admin: 4h vs 8h for POS
    token = create_access_token(user.user_id, user.username, expire_minutes=240)

    # Build permissions map from role
    permissions = (user.role.permissions_json or {}).get(user.role.code, {})

    return AdminLoginResponse(
        access_token=token,
        expires_in=14400,  # 4 hours in seconds
        user={
            "user_id": user.user_id,
            "username": user.username,
            "name": user.name,
            "role": user.role.code,
            "permissions": permissions,
        },
    )
