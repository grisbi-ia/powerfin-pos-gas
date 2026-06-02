"""Integration tests for auth API endpoints."""


class TestLogin:
    async def test_login_success(self, client):
        r = await client.post("/api/pos/auth/login", json={
            "username": "carlos", "pin": "1234"
        })
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["user"]["name"] == "Carlos Sarmiento"
        assert data["user"]["role"] == "DISPATCHER"
        assert data["expires_in"] == 28800

    async def test_login_wrong_pin(self, client):
        r = await client.post("/api/pos/auth/login", json={
            "username": "carlos", "pin": "0000"
        })
        assert r.status_code == 401
        assert "error" in r.json() or "detail" in r.json()

    async def test_login_nonexistent_user(self, client):
        r = await client.post("/api/pos/auth/login", json={
            "username": "ghost", "pin": "1234"
        })
        assert r.status_code == 401

    async def test_login_missing_fields(self, client):
        r = await client.post("/api/pos/auth/login", json={})
        assert r.status_code == 422


class TestAuthRequired:
    async def test_no_token_returns_401(self, client):
        r = await client.get("/api/pos/config")
        assert r.status_code == 401

    async def test_invalid_token_returns_401(self, client):
        r = await client.get("/api/pos/config", headers={
            "Authorization": "Bearer notarealtoken12345"
        })
        assert r.status_code == 401

    async def test_valid_token_accesses_resource(self, client, auth_headers):
        r = await client.get("/api/pos/config", headers=auth_headers)
        assert r.status_code == 200
