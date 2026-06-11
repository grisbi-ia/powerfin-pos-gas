import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestCashBalanceValidation:
    """Cash movements — no longer restrict negative balance (employee can deposit all physical cash)."""

    async def _open_shift(self, client: AsyncClient, headers: dict, opening: float = 0.0):
        r = await client.post("/api/pos/shifts/open", headers=headers, json={
            "opening_cash": opening, "user_name": "Test"
        })
        return r.json()["shift_id"]

    async def test_expense_allows_negative_balance(self, client, auth_headers):
        """EXPENSE is now always allowed — negative balance shows as shortage at close."""
        shift_id = await self._open_shift(client, auth_headers, opening=50.0)

        # Expense of $100 with only $50 available → now allowed (balance goes to -$50)
        r = await client.post("/api/pos/cash-movements", headers=auth_headers, json={
            "shift_id": shift_id, "type": "EXPENSE", "amount": 100.0,
            "observation": "Allowed — negative balance OK"
        })
        assert r.status_code == 201

    async def test_deposit_allows_negative_balance(self, client, auth_headers):
        """DEPOSIT is now always allowed."""
        shift_id = await self._open_shift(client, auth_headers, opening=10.0)

        r = await client.post("/api/pos/cash-movements", headers=auth_headers, json={
            "shift_id": shift_id, "type": "DEPOSIT", "amount": 200.0,
            "observation": "All cash deposited"
        })
        assert r.status_code == 201

    async def test_income_always_allowed(self, client, auth_headers):
        """INCOME movements are always allowed."""
        shift_id = await self._open_shift(client, auth_headers, opening=0.0)

        r = await client.post("/api/pos/cash-movements", headers=auth_headers, json={
            "shift_id": shift_id, "type": "INCOME", "amount": 999.99,
            "observation": "Depósito grande"
        })
        assert r.status_code == 201

    async def test_transfer_allows_negative_balance(self, client, auth_headers):
        """Transfer is now always allowed — negative balance OK."""
        shift_id = await self._open_shift(client, auth_headers, opening=30.0)

        # Need a recipient with an open shift
        admin_login = await client.post("/api/pos/auth/login", json={"username": "admin", "pin": "1234"})
        admin_token = admin_login.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        await client.post("/api/pos/shifts/open", headers=admin_headers, json={"opening_cash": 0, "user_name": "Admin"})

        # Transfer $50 with only $30 available → now allowed
        r = await client.post("/api/pos/transfers", headers=auth_headers, json={
            "from_shift_id": shift_id,
            "to_user_id": 1,
            "amount": 50.0,
            "observation": "Allowed — negative OK"
        })
        assert r.status_code == 201
