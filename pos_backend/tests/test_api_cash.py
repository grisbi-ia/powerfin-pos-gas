"""Tests for cash movements — negative balance prevention."""

import pytest


class TestCash:
    """Cash movement validation tests."""

    async def _open_shift(self, client, auth_headers, opening=50.0):
        r = await client.post("/api/pos/shifts/open", headers=auth_headers, json={
            "opening_cash": opening
        })
        assert r.status_code in (200, 201)
        data = r.json()
        return data["shift_id"]

    async def test_expense_rejected_when_insufficient_balance(self, client, auth_headers):
        """Block EXPENSE that exceeds available cash."""
        shift_id = await self._open_shift(client, auth_headers, opening=50.0)

        # Try expense of $100 → should fail (only $50 available)
        r = await client.post("/api/pos/cash-movements", headers=auth_headers, json={
            "shift_id": shift_id, "type": "EXPENSE", "amount": 100.0,
            "observation": "Should fail"
        })
        assert r.status_code == 400
        assert "Saldo insuficiente" in r.json()["detail"]

    async def test_expense_allowed_within_balance(self, client, auth_headers):
        """Allow EXPENSE within available cash."""
        shift_id = await self._open_shift(client, auth_headers, opening=50.0)

        # Add income first
        await client.post("/api/pos/cash-movements", headers=auth_headers, json={
            "shift_id": shift_id, "type": "INCOME", "amount": 30.0,
            "observation": "Venta aceite"
        })

        # Now expense $60 (available: $50 + $30 = $80) → should work
        r = await client.post("/api/pos/cash-movements", headers=auth_headers, json={
            "shift_id": shift_id, "type": "EXPENSE", "amount": 60.0,
            "observation": "Pago proveedor"
        })
        assert r.status_code == 201

        # Remaining balance: $80 - $60 = $20
        # Try expense $30 → should fail
        r = await client.post("/api/pos/cash-movements", headers=auth_headers, json={
            "shift_id": shift_id, "type": "EXPENSE", "amount": 30.0,
            "observation": "Should fail"
        })
        assert r.status_code == 400
        assert "Saldo insuficiente" in r.json()["detail"]

        # Expense $15 → should work
        r = await client.post("/api/pos/cash-movements", headers=auth_headers, json={
            "shift_id": shift_id, "type": "EXPENSE", "amount": 15.0,
            "observation": "Compra material"
        })
        assert r.status_code == 201

    async def test_income_always_allowed(self, client, auth_headers):
        """INCOME movements are always allowed (no balance check)."""
        shift_id = await self._open_shift(client, auth_headers, opening=0.0)

        r = await client.post("/api/pos/cash-movements", headers=auth_headers, json={
            "shift_id": shift_id, "type": "INCOME", "amount": 999.99,
            "observation": "Depósito grande"
        })
        assert r.status_code == 201

    async def test_transfer_rejected_when_insufficient_balance(self, client, auth_headers):
        """Block transfer that exceeds available cash."""
        shift_id = await self._open_shift(client, auth_headers, opening=30.0)

        # Try transfer of $50 → should fail (only $30 available)
        r = await client.post("/api/pos/transfers", headers=auth_headers, json={
            "from_shift_id": shift_id,
            "to_user_id": 1,
            "amount": 50.0,
            "observation": "Should fail"
        })
        assert r.status_code == 400
        assert "Saldo insuficiente" in r.json()["detail"]

    async def test_safe_drop_rejected_when_insufficient_balance(self, client, auth_headers):
        """Block safe drop that exceeds available cash."""
        shift_id = await self._open_shift(client, auth_headers, opening=30.0)

        # Try safe drop of $50 → should fail (only $30 available)
        r = await client.post("/api/pos/transfers", headers=auth_headers, json={
            "from_shift_id": shift_id,
            "to_user_id": 0,
            "amount": 50.0,
            "observation": "Should fail"
        })
        assert r.status_code == 400
        assert "Saldo insuficiente" in r.json()["detail"]
