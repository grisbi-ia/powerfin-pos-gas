"""Integration tests for config, vehicles, customers, products, prices APIs."""


class TestConfigAPI:
    async def test_config_returns_full_data(self, client, auth_headers):
        r = await client.get("/api/pos/config", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["location"]["name"] == "TEST"
        assert len(data["dispensers"]) == 1
        assert data["dispensers"][0]["name"] == "Surtidor DIESEL"
        assert len(data["dispensers"][0]["sides"]["A"]) == 1
        assert len(data["dispensers"][0]["sides"]["B"]) == 1
        assert len(data["grades"]) == 2
        assert len(data["payment_methods"]) == 4
        assert len(data["price_lists"]) == 2
        assert data["polling"]["enabled"] is True


class TestVehiclesAPI:
    async def test_vehicle_found(self, client, auth_headers):
        r = await client.get("/api/pos/vehicles?plate=ABC1234", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["vehicle_found"] is True
        assert data["owner"]["name"] == "Juan Carlos Pérez"
        assert data["price_list"] == "VIP"

    async def test_vehicle_not_found(self, client, auth_headers):
        r = await client.get("/api/pos/vehicles?plate=ZZZ9999", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["vehicle_found"] is False
        assert data["owner"] is None
        assert data["price_list"] == "STANDARD"


class TestCustomersAPI:
    async def test_search_by_name(self, client, auth_headers):
        r = await client.get("/api/pos/customers?q=juan", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        assert data[0]["name"] == "Juan Carlos Pérez"

    async def test_search_by_plate(self, client, auth_headers):
        r = await client.get("/api/pos/customers?q=ABC1234", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        assert any("ABC1234" in c["plates"] for c in data)

    async def test_get_by_id(self, client, auth_headers):
        r = await client.get("/api/pos/customers/by-id?id_type=CED&id_number=0912345678", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "Juan Carlos Pérez"

    async def test_get_by_id_not_found(self, client, auth_headers):
        r = await client.get("/api/pos/customers/by-id?id_type=CED&id_number=9999999999", headers=auth_headers)
        assert r.status_code == 404

    async def test_create_customer(self, client, auth_headers):
        r = await client.post("/api/pos/customers", headers=auth_headers, json={
            "id_type": "CED", "id_number": "1712345678",
            "name": "Nuevo Cliente", "email": "nuevo@test.com",
            "plate": "NEW1234"
        })
        assert r.status_code == 201
        data = r.json()
        assert data["customer_id"] == "1712345678"
        assert data["price_list"] == "STANDARD"


class TestProductsAPI:
    async def test_list_products(self, client, auth_headers):
        r = await client.get("/api/pos/products", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 3
        codes = [p["code"] for p in data]
        assert "DIESEL" in codes
        assert "SUPER" in codes

    async def test_list_categories(self, client, auth_headers):
        r = await client.get("/api/pos/product-categories", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 2
        codes = [c["code"] for c in data]
        assert "FUEL" in codes and "OIL" in codes

    async def test_list_price_lists(self, client, auth_headers):
        r = await client.get("/api/pos/price-lists", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 2
        codes = [p["code"] for p in data]
        assert "STANDARD" in codes
        assert "VIP" in codes

    async def test_list_dispatch_types(self, client, auth_headers):
        r = await client.get("/api/pos/dispatch-types", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 4
        codes = [dt["code"] for dt in data]
        assert "SALE" in codes
        assert "CREDIT" in codes
        assert "CALIBRATION" in codes


class TestPricesAPI:
    async def test_price_by_vehicle(self, client, auth_headers):
        r = await client.get("/api/pos/prices?vehicleId=ABC1234&gradeId=DIESEL", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["price_list"] == "VIP"
        assert data["grade_id"] == "DIESEL"

    async def test_price_by_customer(self, client, auth_headers):
        r = await client.get("/api/pos/prices?customerId=0912345678&gradeId=DIESEL", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["grade_id"] == "DIESEL"

    async def test_price_default(self, client, auth_headers):
        r = await client.get("/api/pos/prices?gradeId=SUPER", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["price_list"] == "STANDARD"
