"""Integration tests for credit contracts and cash APIs."""

from decimal import Decimal


class TestCreditContractsAPI:
    async def test_list_contracts(self, client, auth_headers):
        r = await client.get("/api/pos/credit-contracts", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["contract_code"] == "CT-001"
        assert data[0]["contract_type"] == "INDEFINIDO"
        assert float(data[0]["available"]) == 5000.00

    async def test_get_contract(self, client, auth_headers):
        r = await client.get("/api/pos/credit-contracts/1", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["contract_code"] == "CT-001"
        assert len(data["vehicles"]) == 1
        assert len(data["products"]) == 1

    async def test_get_available(self, client, auth_headers):
        r = await client.get("/api/pos/credit-contracts/1/available", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert float(data["cupo"]) == 5000.00
        assert float(data["available"]) == 5000.00
        assert float(data["consumed"]) == 0.00

    async def test_update_contract(self, client, auth_headers):
        r = await client.put("/api/pos/credit-contracts/1", headers=auth_headers, json={
            "cupo": 10000.00, "contract_type": "NO_INDEFINIDO"
        })
        assert r.status_code == 200

        r = await client.get("/api/pos/credit-contracts/1", headers=auth_headers)
        data = r.json()
        assert float(data["cupo"]) == 10000.00
        assert data["contract_type"] == "NO_INDEFINIDO"


class TestCashAPI:
    async def _open_shift(self, client, auth_headers):
        r = await client.post("/api/pos/shifts/open", headers=auth_headers, json={
            "opening_cash": 100, "user_name": "Carlos Sarmiento"
        })
        return r.json()["shift_id"]

    async def test_create_income(self, client, auth_headers):
        shift_id = await self._open_shift(client, auth_headers)
        r = await client.post("/api/pos/cash-movements", headers=auth_headers, json={
            "shift_id": shift_id, "type": "INCOME", "amount": 50, "observation": "Cambio"
        })
        assert r.status_code == 201
        data = r.json()
        assert data["type"] == "INCOME"
        assert data["running_balance"] == 50.0

    async def test_running_balance_accumulates(self, client, auth_headers):
        shift_id = await self._open_shift(client, auth_headers)

        r1 = await client.post("/api/pos/cash-movements", headers=auth_headers, json={
            "shift_id": shift_id, "type": "INCOME", "amount": 100, "observation": ""
        })
        assert r1.json()["running_balance"] == 100.0

        r2 = await client.post("/api/pos/cash-movements", headers=auth_headers, json={
            "shift_id": shift_id, "type": "EXPENSE", "amount": 30, "observation": ""
        })
        assert r2.json()["running_balance"] == 70.0

    async def test_get_movements(self, client, auth_headers):
        shift_id = await self._open_shift(client, auth_headers)
        await client.post("/api/pos/cash-movements", headers=auth_headers, json={
            "shift_id": shift_id, "type": "INCOME", "amount": 50, "observation": ""
        })
        r = await client.get(f"/api/pos/shifts/{shift_id}/cash-movements", headers=auth_headers)
        assert r.status_code == 200
        assert len(r.json()) >= 1

    async def test_get_summary(self, client, auth_headers):
        shift_id = await self._open_shift(client, auth_headers)
        await client.post("/api/pos/cash-movements", headers=auth_headers, json={
            "shift_id": shift_id, "type": "INCOME", "amount": 50, "observation": ""
        })
        r = await client.get(f"/api/pos/shifts/{shift_id}/cash-summary", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert float(data["total_income"]) == 50.0
        assert float(data["current_balance"]) == 150.0  # 100 opening + 50 income

    async def test_transfer(self, client, auth_headers):
        shift_id = await self._open_shift(client, auth_headers)
        r = await client.post("/api/pos/transfers", headers=auth_headers, json={
            "from_shift_id": shift_id, "to_user_id": 0, "amount": 50, "observation": "A caja fuerte"
        })
        assert r.status_code == 201
        data = r.json()
        assert data["to_user_name"] == "Caja Fuerte"
        assert float(data["amount"]) == 50.0

    async def test_users_online(self, client, auth_headers):
        await self._open_shift(client, auth_headers)
        r = await client.get("/api/pos/users/online", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        # Should have at least the current user + Caja Fuerte
        assert len(data) >= 2
        names = [u["name"] for u in data]
        assert "Carlos Sarmiento" in names
        assert "Caja Fuerte" in names
