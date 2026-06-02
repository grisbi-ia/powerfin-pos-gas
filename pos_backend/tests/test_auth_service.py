"""Unit tests for auth_service."""

import pytest
from app.services.auth_service import (
    create_access_token,
    decode_access_token,
    hash_pin,
    verify_pin,
    authenticate_user,
)
from app.config import settings


class TestPinHashing:
    def test_hash_is_not_plaintext(self):
        hashed = hash_pin("1234")
        assert hashed != "1234"
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    def test_verify_correct_pin(self):
        hashed = hash_pin("9999")
        assert verify_pin("9999", hashed) is True

    def test_verify_wrong_pin(self):
        hashed = hash_pin("1234")
        assert verify_pin("5678", hashed) is False

    def test_different_salts_produce_different_hashes(self):
        h1 = hash_pin("1234")
        h2 = hash_pin("1234")
        assert h1 != h2
        assert verify_pin("1234", h1)
        assert verify_pin("1234", h2)


class TestJWT:
    def test_create_and_decode_valid(self):
        token = create_access_token(42, "testuser")
        payload = decode_access_token(token)
        assert payload["sub"] == "42"
        assert payload["username"] == "testuser"

    def test_decode_invalid_token(self):
        with pytest.raises(Exception):
            decode_access_token("not.a.valid.token")

    def test_decode_tampered_token(self):
        token = create_access_token(1, "admin")
        tampered = token[:-5] + "xxxxx"
        with pytest.raises(Exception):
            decode_access_token(tampered)

    def test_token_contains_expiry(self):
        token = create_access_token(1, "user")
        payload = decode_access_token(token)
        assert "exp" in payload


class TestAuthenticateUser:
    @pytest.mark.asyncio
    async def test_valid_credentials(self, db):
        user = await authenticate_user(db, "carlos", "1234")
        assert user is not None
        assert user.username == "carlos"
        assert user.name == "Carlos Sarmiento"

    @pytest.mark.asyncio
    async def test_wrong_password(self, db):
        user = await authenticate_user(db, "carlos", "0000")
        assert user is None

    @pytest.mark.asyncio
    async def test_nonexistent_user(self, db):
        user = await authenticate_user(db, "noexiste", "1234")
        assert user is None

    @pytest.mark.asyncio
    async def test_case_insensitive_username(self, db):
        user = await authenticate_user(db, "Carlos", "1234")
        assert user is not None
        assert user.username == "carlos"
