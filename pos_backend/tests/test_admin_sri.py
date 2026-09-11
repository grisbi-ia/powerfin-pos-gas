"""Tests for the admin SRI/Key49 monitoring module (Phase 1, read-only).

Covers: taxonomy classifier, feature-flag gate (default off), and that the
read-only endpoints work when enabled. The module must never be reachable
while disabled.
"""

import pytest

from app.models.company import SystemConfig
from app.services.sri_monitor_service import classify_problem


def _admin_headers():
    from app.services.auth_service import create_access_token
    token = create_access_token(1, "admin", expire_minutes=240)
    return {"Authorization": f"Bearer {token}"}


def _dispatcher_headers():
    from app.services.auth_service import create_access_token
    token = create_access_token(2, "carlos")
    return {"Authorization": f"Bearer {token}"}


async def _enable_monitor(db):
    db.add(SystemConfig(key="sri_monitor_enabled", value="true"))
    await db.commit()


class TestClassifyProblem:
    def test_authorized_is_ok(self):
        assert classify_problem("AUTHORIZED", True) == "OK"
        assert classify_problem("NOTIFIED", True) == "OK"

    def test_never_sent(self):
        assert classify_problem("PENDING", False) == "NEVER_SENT"

    def test_pending_with_key49_id_is_stale(self):
        assert classify_problem("PENDING", True) == "PENDING_SENT"

    def test_key49_failed_vs_invalid_data(self):
        assert classify_problem("FAILED", True) == "KEY49_FAILED"
        assert classify_problem("FAILED", False) == "INVALID_DATA"

    def test_in_progress_and_rejected(self):
        assert classify_problem("RECEIVED", True) == "IN_PROGRESS"
        assert classify_problem("REJECTED", True) == "REJECTED"


class TestFeatureFlagGate:
    async def test_metrics_disabled_by_default(self, client):
        """With no sri_monitor_enabled flag the module returns 403 (zero queries)."""
        r = await client.get("/api/admin/sri/metrics", headers=_admin_headers())
        assert r.status_code == 403
        assert "desactivado" in r.json().get("detail", "")

    async def test_documents_disabled_by_default(self, client):
        r = await client.get("/api/admin/sri/documents", headers=_admin_headers())
        assert r.status_code == 403

    async def test_health_disabled_by_default(self, client):
        r = await client.get("/api/admin/sri/health", headers=_admin_headers())
        assert r.status_code == 403


class TestEnabled:
    async def test_metrics_shape(self, client, db):
        await _enable_monitor(db)
        r = await client.get("/api/admin/sri/metrics", headers=_admin_headers())
        assert r.status_code == 200, r.text
        data = r.json()
        for key in ("total", "authorized", "in_progress", "problems_total",
                    "success_rate", "by_status", "problems", "by_day"):
            assert key in data
        assert data["problems_total"] >= 0

    async def test_documents_paginated(self, client, db):
        await _enable_monitor(db)
        r = await client.get("/api/admin/sri/documents?page=1&page_size=10",
                             headers=_admin_headers())
        assert r.status_code == 200, r.text
        data = r.json()
        assert set(("items", "total", "page", "page_size", "pages")) <= set(data)

    async def test_health(self, client, db):
        await _enable_monitor(db)
        r = await client.get("/api/admin/sri/health", headers=_admin_headers())
        assert r.status_code == 200, r.text
        data = r.json()
        assert "key49_configured" in data
        assert "last_24h" in data

    async def test_document_detail_404(self, client, db):
        await _enable_monitor(db)
        r = await client.get("/api/admin/sri/documents/999999",
                             headers=_admin_headers())
        assert r.status_code == 404

    async def test_dispatcher_forbidden(self, client, db):
        await _enable_monitor(db)
        r = await client.get("/api/admin/sri/metrics", headers=_dispatcher_headers())
        assert r.status_code == 403
