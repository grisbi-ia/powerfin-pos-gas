"""Integration tests for shifts and dispatch APIs."""

from datetime import datetime, timezone


class TestShiftAPI:
    async def test_open_shift(self, client, auth_headers):
        r = await client.post("/api/pos/shifts/open", headers=auth_headers, json={
            "opening_cash": 0, "user_name": "Carlos Sarmiento", "notes": ""
        })
        assert r.status_code == 201
        data = r.json()
        assert data["status"] == "OPEN"
        assert data["user_name"] == "Carlos Sarmiento"
        assert data["shift_id"] > 0

    async def test_get_current_shift(self, client, auth_headers):
        # Open first
        await client.post("/api/pos/shifts/open", headers=auth_headers, json={
            "opening_cash": 0, "user_name": "Carlos Sarmiento"
        })
        r = await client.get("/api/pos/shifts/current", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data is not None
        assert data["status"] == "OPEN"

    async def test_close_shift(self, client, auth_headers):
        # Open first
        await client.post("/api/pos/shifts/open", headers=auth_headers, json={
            "opening_cash": 100, "user_name": "Carlos Sarmiento"
        })
        r = await client.get("/api/pos/shifts/current", headers=auth_headers)
        shift_id = r.json()["shift_id"]

        r = await client.post(f"/api/pos/shifts/{shift_id}/close", headers=auth_headers, json={
            "notes": ""
        })
        assert r.status_code == 200
        data = r.json()
        assert data["shift_id"] == shift_id
        assert float(data["surplus"]) == 0
        assert float(data["shortage"]) == 100.0  # opening cash not zeroed = faltante


class TestDispatchAPI:
    async def _open_shift(self, client, auth_headers):
        await client.post("/api/pos/shifts/open", headers=auth_headers, json={
            "opening_cash": 0, "user_name": "Carlos Sarmiento"
        })

    async def test_create_dispatch(self, client, auth_headers):
        await self._open_shift(client, auth_headers)
        r = await client.post("/api/pos/dispatches", headers=auth_headers, json={
            "dispenser_id": 1, "hose_id": 1, "side": "A",
            "preset_type": "MONEY", "preset_value": "20.00",
            "unit_price": 3.103, "payment_method_id": 1,
            "customer_name": "Juan Carlos Pérez",
            "plate": "ABC1234",
            "authorized_by": "Carlos Sarmiento",
            "dispatch_type_code": "SALE",
            "items": [
                {"product_id": 1, "quantity": 6.44, "unit_price": 3.103, "tax_rate": 0.12}
            ]
        })
        assert r.status_code == 201
        data = r.json()
        assert data["status"] == "PENDING"
        assert data["order_id"].startswith("OV-")

    async def test_create_dispatch_conflict_same_hose(self, client, auth_headers):
        """409 Conflict when two dispatchers try to authorize the same hose."""
        await self._open_shift(client, auth_headers)
        body = {
            "dispenser_id": 1, "hose_id": 1, "side": "A",
            "preset_type": "MONEY", "preset_value": "20.00",
            "unit_price": 3.103, "payment_method_id": 1,
            "dispatch_type_code": "SALE",
            "items": [
                {"product_id": 1, "quantity": 6.44, "unit_price": 3.103, "tax_rate": 0.12}
            ]
        }
        # First dispatch — should succeed
        r = await client.post("/api/pos/dispatches", headers=auth_headers, json=body)
        assert r.status_code == 201

        # Second dispatch on same hose — should be rejected with 409
        r = await client.post("/api/pos/dispatches", headers=auth_headers, json=body)
        assert r.status_code == 409
        assert "en curso" in r.json()["detail"]

    async def test_complete_dispatch(self, client, auth_headers):
        await self._open_shift(client, auth_headers)
        r = await client.post("/api/pos/dispatches", headers=auth_headers, json={
            "dispenser_id": 1, "hose_id": 1, "side": "A",
            "preset_type": "MONEY", "preset_value": "20.00",
            "unit_price": 3.103, "payment_method_id": 1,
            "dispatch_type_code": "SALE",
            "items": [{"product_id": 1, "quantity": 1, "unit_price": 3.103, "tax_rate": 0}]
        })
        order_id = r.json()["order_id"]

        r = await client.post(f"/api/pos/dispatches/{order_id}/complete", headers=auth_headers, json={
            "order_id": order_id, "fusion_sale_id": "100",
            "volume": "1.0", "amount": 3.103,
            "unit_price": 3.103, "payment_method_id": 1
        })
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    async def test_complete_idempotent(self, client, auth_headers):
        await self._open_shift(client, auth_headers)
        r = await client.post("/api/pos/dispatches", headers=auth_headers, json={
            "dispenser_id": 1, "hose_id": 1, "side": "A",
            "preset_type": "MONEY", "preset_value": "10.00",
            "unit_price": 3.103, "payment_method_id": 1,
            "dispatch_type_code": "SALE",
            "items": [{"product_id": 1, "quantity": 1, "unit_price": 3.103, "tax_rate": 0}]
        })
        order_id = r.json()["order_id"]

        body = {"order_id": order_id, "amount": 3.103, "unit_price": 3.103, "volume": "1", "payment_method_id": 1, "fusion_sale_id": "100"}
        r1 = await client.post(f"/api/pos/dispatches/{order_id}/complete", headers=auth_headers, json=body)
        r2 = await client.post(f"/api/pos/dispatches/{order_id}/complete", headers=auth_headers, json=body)
        assert r1.status_code == 200
        assert r2.status_code == 200  # Idempotent

    async def test_cancel_dispatch(self, client, auth_headers):
        await self._open_shift(client, auth_headers)
        r = await client.post("/api/pos/dispatches", headers=auth_headers, json={
            "dispenser_id": 1, "hose_id": 1, "side": "A",
            "preset_type": "MONEY", "preset_value": "10.00",
            "unit_price": 3.103, "payment_method_id": 1,
            "dispatch_type_code": "SALE",
            "items": [{"product_id": 1, "quantity": 1, "unit_price": 3.103, "tax_rate": 0}]
        })
        order_id = r.json()["order_id"]

        r = await client.post(f"/api/pos/dispatches/{order_id}/cancel", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    async def test_collect_with_payments(self, client, auth_headers):
        await self._open_shift(client, auth_headers)
        r = await client.post("/api/pos/dispatches", headers=auth_headers, json={
            "dispenser_id": 1, "hose_id": 1, "side": "A",
            "preset_type": "MONEY", "preset_value": "50.00",
            "unit_price": 50.00, "payment_method_id": 1,
            "dispatch_type_code": "SALE",
            "items": [{"product_id": 1, "quantity": 10, "unit_price": 5.00, "tax_rate": 0}]
        })
        order_id = r.json()["order_id"]
        await client.post(f"/api/pos/dispatches/{order_id}/complete", headers=auth_headers, json={
            "order_id": order_id, "amount": 50, "unit_price": 5, "volume": "10", "payment_method_id": 1, "fusion_sale_id": "101"
        })

        r = await client.post(f"/api/pos/dispatches/{order_id}/collect", headers=auth_headers, json={
            "collected_by_shift_id": 1,
            "payment_method_id": 1,
            "collected_amount": 60,
            "change_amount": 10,
            "payments": [
                {"payment_method_id": 1, "amount": 40, "reference_code": None},
                {"payment_method_id": 4, "amount": 20, "reference_code": "REF123"},
            ]
        })
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "COLLECTED"
        assert float(data["change_amount"]) == 10.0
