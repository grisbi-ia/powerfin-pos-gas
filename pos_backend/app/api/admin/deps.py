"""Admin auth dependencies — role-based access control."""

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import Role, User


async def get_admin_user(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Verify the current user has an admin-capable role (ADMIN or SUPERVISOR).

    Raises 403 if the user has role DISPATCHER or any non-admin role.
    Used as a FastAPI dependency on all /api/admin/* endpoints.
    """
    role = await db.get(Role, current_user.role_id)
    if not role or role.code not in ("ADMIN", "SUPERVISOR"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso restringido — se requiere rol ADMIN o SUPERVISOR",
        )
    return current_user


def require_permission(resource: str, action: str):
    """Factory: returns a FastAPI dependency that checks a granular permission.

    Usage:
        @router.get("/users", dependencies=[Depends(require_permission("users", "read"))])

    The dependency reads role.permissions_json and checks the nested key path:
        permissions_json[role_code][resource] must contain `action`.

    If the role has no permissions_json defined (None or {}), ADMIN and
    SUPERVISOR roles are granted full access. DISPATCHER is always denied
    (already caught by get_admin_user).
    """
    async def checker(
        current_user: User = Depends(get_admin_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        role = await db.get(Role, current_user.role_id)
        perms = (role.permissions_json or {}) if role else {}

        # If no permissions configured at all, grant access to admin roles.
        # This is the safe default — permissions_json can be added later
        # to restrict specific actions without breaking existing setups.
        if not perms:
            return current_user

        # Convention: {"all": true} means full access to everything
        if perms.get("all") is True:
            return current_user

        # Expected format: {role_code: {resource: [actions]}}
        role_perms = perms.get(role.code if role else "", {})
        if not isinstance(role_perms, dict):
            role_perms = {}
        allowed = role_perms.get(resource, [])
        if action not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permiso denegado: {action} {resource}",
            )
        return current_user
    return checker
