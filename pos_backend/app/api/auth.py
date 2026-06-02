"""Auth endpoints — login with PIN."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import ErrorResponse, LoginRequest, LoginResponse, UserResponse
from app.services.auth_service import authenticate_user, create_access_token

router = APIRouter(prefix="/api/pos/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={401: {"model": ErrorResponse}},
)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate a user with username and PIN. Returns a JWT token."""
    user = await authenticate_user(db, body.username, body.pin)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
        )

    token = create_access_token(user.user_id, user.username)
    return LoginResponse(
        access_token=token,
        expires_in=28800,
        user=UserResponse(
            user_id=user.user_id,
            name=user.name,
            role=user.role.code if user.role else "DISPATCHER",
        ),
    )
