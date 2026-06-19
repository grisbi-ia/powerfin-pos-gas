"""Authentication service — bcrypt password hashing + JWT tokens."""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.user import User


def hash_pin(pin: str) -> str:
    """Hash a PIN using bcrypt."""
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()


def verify_pin(pin: str, pin_hash: str) -> bool:
    """Verify a PIN against its bcrypt hash."""
    return bcrypt.checkpw(pin.encode(), pin_hash.encode())


def create_access_token(user_id: int, username: str, expire_minutes: int | None = None) -> str:
    """Create a JWT access token.

    expire_minutes overrides settings.jwt_expire_minutes when provided.
    POS login uses the default (480 min = 8h).
    Admin login passes 240 min = 4h.
    """
    minutes = expire_minutes if expire_minutes is not None else settings.jwt_expire_minutes
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises on invalid/expired."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


async def authenticate_user(db: AsyncSession, username: str, pin: str) -> User | None:
    """Validate credentials and return the user, or None."""
    result = await db.execute(
        select(User)
        .where(User.username == username.lower())
        .options(selectinload(User.role))
    )
    user = result.scalar_one_or_none()
    if user and verify_pin(pin, user.pin_hash):
        return user
    return None
