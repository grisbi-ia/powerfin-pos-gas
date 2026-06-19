"""Tests for /api/pos/vehicles/predefined and /predefined/next endpoints."""

from datetime import datetime, timedelta

from sqlalchemy import text as sa_text
from zoneinfo import ZoneInfo

from app.models import Dispatch, Person, Vehicle
from app.models.shift import Shift
from app.services.auth_service import create_access_token


class TestPredefinedVehicles:
    async def test_predefined_empty_when_none_flagged(self, client, db):
        """GET /predefined returns empty list when no vehicles have allow_container_sale=True."""
        token = create_access_token(1, "admin")
        resp = await client.get(
            "/api/pos/vehicles/predefined",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_predefined_returns_flagged_vehicles(self, client, db):
        """GET /predefined returns only vehicles with allow_container_sale=True."""
        v1 = await db.get(Vehicle, 1)
        v1.allow_container_sale = True
        await db.commit()

        token = create_access_token(1, "admin")
        resp = await client.get(
            "/api/pos/vehicles/predefined",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["vehicle_id"] == 1
        assert data[0]["plate"] == "ABC1234"
        assert data[0]["owner_name"] == "Juan Carlos Pérez"


class TestPredefinedNext:
    async def test_next_404_when_none_flagged(self, client, db):
        """GET /predefined/next returns 404 when no vehicles have allow_container_sale=True."""
        token = create_access_token(1, "admin")
        resp = await client.get(
            "/api/pos/vehicles/predefined/next",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404
        assert "No hay vehículos" in resp.json()["detail"]

    async def test_next_picks_only_flagged(self, client, db):
        """GET /predefined/next picks the only flagged vehicle when it has no dispatches."""
        v1 = await db.get(Vehicle, 1)
        v1.allow_container_sale = True
        await db.commit()

        token = create_access_token(1, "admin")
        resp = await client.get(
            "/api/pos/vehicles/predefined/next",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["vehicle_id"] == 1
        assert data["plate"] == "ABC1234"

    async def test_next_picks_least_used_today(self, client, db):
        """GET /predefined/next returns the vehicle with fewer dispatches today."""
        v1 = await db.get(Vehicle, 1)
        v1.allow_container_sale = True
        v2 = await db.get(Vehicle, 2)
        v2.allow_container_sale = True
        await db.commit()

        tz = ZoneInfo("America/Guayaquil")
        now = datetime.now(tz)

        shift = Shift(user_id=2, status="OPEN")
        db.add(shift)
        await db.flush()

        dispatch_type = (await db.execute(
            sa_text("SELECT dispatch_type_id FROM dispatch_types WHERE code = 'SALE'")
        )).scalar_one()

        # 3 dispatches for vehicle 1, 1 dispatch for vehicle 2
        for i in range(3):
            db.add(Dispatch(
                order_id=f"T-1-{i}",
                shift_id=shift.shift_id,
                dispenser_id=1,
                dispatch_type_id=dispatch_type,
                vehicle_id=1,
                person_id=1,
                created_at=now,
                status="COMPLETED",
            ))

        db.add(Dispatch(
            order_id="T-2-0",
            shift_id=shift.shift_id,
            dispenser_id=1,
            dispatch_type_id=dispatch_type,
            vehicle_id=2,
            person_id=2,
            created_at=now,
            status="COMPLETED",
        ))
        await db.commit()

        token = create_access_token(1, "admin")
        resp = await client.get(
            "/api/pos/vehicles/predefined/next",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["vehicle_id"] == 2  # fewer dispatches (1 vs 3)

    async def test_next_ignores_cancelled_dispatches(self, client, db):
        """GET /predefined/next does not count CANCELLED dispatches."""
        v1 = await db.get(Vehicle, 1)
        v1.allow_container_sale = True
        v2 = await db.get(Vehicle, 2)
        v2.allow_container_sale = True
        await db.commit()

        tz = ZoneInfo("America/Guayaquil")
        now = datetime.now(tz)

        shift = Shift(user_id=2, status="OPEN")
        db.add(shift)
        await db.flush()

        dispatch_type = (await db.execute(
            sa_text("SELECT dispatch_type_id FROM dispatch_types WHERE code = 'SALE'")
        )).scalar_one()

        # 5 CANCELLED for vehicle 1 → counts as 0
        for i in range(5):
            db.add(Dispatch(
                order_id=f"TC-1-{i}",
                shift_id=shift.shift_id,
                dispenser_id=1,
                dispatch_type_id=dispatch_type,
                vehicle_id=1,
                person_id=1,
                created_at=now,
                status="CANCELLED",
            ))

        # 2 COMPLETED for vehicle 2
        for i in range(2):
            db.add(Dispatch(
                order_id=f"TC-2-{i}",
                shift_id=shift.shift_id,
                dispenser_id=1,
                dispatch_type_id=dispatch_type,
                vehicle_id=2,
                person_id=2,
                created_at=now,
                status="COMPLETED",
            ))
        await db.commit()

        token = create_access_token(1, "admin")
        resp = await client.get(
            "/api/pos/vehicles/predefined/next",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Vehicle 1 had 5 CANCELLED → counts as 0 → is the least used
        assert data["vehicle_id"] == 1

    async def test_next_ignores_old_dispatches(self, client, db):
        """GET /predefined/next only counts dispatches from today (Guayaquil time)."""
        v1 = await db.get(Vehicle, 1)
        v1.allow_container_sale = True
        v2 = await db.get(Vehicle, 2)
        v2.allow_container_sale = True
        await db.commit()

        tz = ZoneInfo("America/Guayaquil")
        now = datetime.now(tz)
        # Yesterday at same time
        yesterday = now - timedelta(days=1)

        shift = Shift(user_id=2, status="OPEN")
        db.add(shift)
        await db.flush()

        dispatch_type = (await db.execute(
            sa_text("SELECT dispatch_type_id FROM dispatch_types WHERE code = 'SALE'")
        )).scalar_one()

        # 10 dispatches YESTERDAY for vehicle 1 → should not count
        for i in range(10):
            db.add(Dispatch(
                order_id=f"TO-1-{i}",
                shift_id=shift.shift_id,
                dispenser_id=1,
                dispatch_type_id=dispatch_type,
                vehicle_id=1,
                person_id=1,
                created_at=yesterday,
                status="COMPLETED",
            ))

        # 1 dispatch TODAY for vehicle 2
        db.add(Dispatch(
            order_id="TO-2-0",
            shift_id=shift.shift_id,
            dispenser_id=1,
            dispatch_type_id=dispatch_type,
            vehicle_id=2,
            person_id=2,
            created_at=now,
            status="COMPLETED",
        ))
        await db.commit()

        token = create_access_token(1, "admin")
        resp = await client.get(
            "/api/pos/vehicles/predefined/next",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Vehicle 1 has 10 yesterday + 0 today → is the least used
        assert data["vehicle_id"] == 1
