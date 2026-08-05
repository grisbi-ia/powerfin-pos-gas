"""Tests for mechanical meters CRUD (admin) and shift meter readings (POS)."""

import pytest
from sqlalchemy import select

from app.models.mechanical_meter import MechanicalMeter, MeterReading
from app.models.dispenser import Dispenser, Hose
from app.models.product import Grade


# ── Auth Helpers (matching existing test patterns) ──────────────────


def _admin_headers():
    from app.services.auth_service import create_access_token
    token = create_access_token(1, "admin", expire_minutes=240)
    return {"Authorization": f"Bearer {token}"}


def _dispatcher_headers():
    from app.services.auth_service import create_access_token
    token = create_access_token(2, "carlos")
    return {"Authorization": f"Bearer {token}"}


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
async def dispenser_with_hoses(client, db):
    """Create a dispenser with hoses for meter tests."""
    d = Dispenser(code="MET-TEST", name="Test Dispenser Meter",
                   sort_order=99)
    db.add(d)
    await db.flush()

    h1 = Hose(dispenser_id=d.dispenser_id, side="A", fusion_pump_id=1,
              fusion_hose_id=1, grade_id="DIESEL")
    h2 = Hose(dispenser_id=d.dispenser_id, side="B", fusion_pump_id=2,
              fusion_hose_id=1, grade_id="DIESEL")
    db.add_all([h1, h2])
    await db.commit()
    await db.refresh(d)
    return d


# ── Admin CRUD Tests ────────────────────────────────────────────────


class TestAdminMechanicalMeters:
    """Admin CRUD for mechanical meters."""

    async def test_list_meters_empty(self, client, dispenser_with_hoses):
        resp = await client.get(
            f"/api/admin/dispensers/{dispenser_with_hoses.dispenser_id}/meters",
            headers=_admin_headers(),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_product_meter(self, client, dispenser_with_hoses, db):
        # Get a valid grade_id from seed data (DIESEL = grade_id 1)
        grade = await db.get(Grade, 1)
        assert grade is not None

        resp = await client.post(
            f"/api/admin/dispensers/{dispenser_with_hoses.dispenser_id}/meters",
            headers=_admin_headers(),
            json={
                "name": "Medidor Súper",
                "meter_type": "PRODUCT",
                "grade_id": grade.grade_id,
                "sort_order": 1,
            },
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["name"] == "Medidor Súper"
        assert data["meter_type"] == "PRODUCT"
        assert data["grade_id"] == grade.grade_id
        assert data["grade_name"] is not None
        assert data["is_active"] is True

    async def test_create_hose_meter(self, client, dispenser_with_hoses, db):
        # Get a hose from the test dispenser
        hoses_res = await db.execute(
            select(Hose).where(Hose.dispenser_id == dispenser_with_hoses.dispenser_id)
        )
        hoses = hoses_res.scalars().all()
        assert len(hoses) >= 1

        resp = await client.post(
            f"/api/admin/dispensers/{dispenser_with_hoses.dispenser_id}/meters",
            headers=_admin_headers(),
            json={
                "name": "Medidor Lado A",
                "meter_type": "HOSE",
                "hose_id": hoses[0].hose_id,
                "sort_order": 2,
            },
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["meter_type"] == "HOSE"
        assert data["hose_id"] == hoses[0].hose_id
        assert data["hose_side"] == hoses[0].side

    async def test_create_product_meter_missing_grade(self, client,
                                                       dispenser_with_hoses):
        resp = await client.post(
            f"/api/admin/dispensers/{dispenser_with_hoses.dispenser_id}/meters",
            headers=_admin_headers(),
            json={
                "name": "Bad Meter",
                "meter_type": "PRODUCT",
                "grade_id": None,
            },
        )
        assert resp.status_code == 422  # validation error

    async def test_create_hose_meter_missing_hose(self, client,
                                                   dispenser_with_hoses):
        resp = await client.post(
            f"/api/admin/dispensers/{dispenser_with_hoses.dispenser_id}/meters",
            headers=_admin_headers(),
            json={
                "name": "Bad Meter",
                "meter_type": "HOSE",
                "hose_id": None,
            },
        )
        assert resp.status_code == 422

    async def test_create_hose_meter_wrong_dispenser(self, client,
                                                      dispenser_with_hoses, db):
        """Hose must belong to the dispenser it's being added to."""
        # Create another dispenser with its own hose
        d2 = Dispenser(code="WRONG", name="Wrong Dispenser", sort_order=100)
        db.add(d2)
        await db.flush()
        h_other = Hose(dispenser_id=d2.dispenser_id, side="A",
                       fusion_pump_id=9, fusion_hose_id=9, grade_id="DIESEL")
        db.add(h_other)
        await db.commit()

        resp = await client.post(
            f"/api/admin/dispensers/{dispenser_with_hoses.dispenser_id}/meters",
            headers=_admin_headers(),
            json={
                "name": "Wrong Hose Meter",
                "meter_type": "HOSE",
                "hose_id": h_other.hose_id,
            },
        )
        assert resp.status_code == 400
        assert "no pertenece" in resp.json()["detail"].lower()

    async def test_update_meter(self, client, dispenser_with_hoses, db):
        grade = await db.get(Grade, 1)
        m = MechanicalMeter(
            dispenser_id=dispenser_with_hoses.dispenser_id,
            name="Original Name",
            meter_type="PRODUCT",
            grade_id=grade.grade_id,
            sort_order=5,
        )
        db.add(m)
        await db.commit()
        await db.refresh(m)

        resp = await client.put(
            f"/api/admin/dispensers/{dispenser_with_hoses.dispenser_id}/meters/{m.meter_id}",
            headers=_admin_headers(),
            json={"name": "Updated Name", "sort_order": 10},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"
        assert resp.json()["sort_order"] == 10

    async def test_delete_meter_soft(self, client, dispenser_with_hoses, db):
        grade = await db.get(Grade, 1)
        m = MechanicalMeter(
            dispenser_id=dispenser_with_hoses.dispenser_id,
            name="To Delete", meter_type="PRODUCT",
            grade_id=grade.grade_id, sort_order=99,
        )
        db.add(m)
        await db.commit()
        await db.refresh(m)

        resp = await client.delete(
            f"/api/admin/dispensers/{dispenser_with_hoses.dispenser_id}/meters/{m.meter_id}",
            headers=_admin_headers(),
        )
        assert resp.status_code == 204

        # Verify soft-deleted
        await db.refresh(m)
        assert m.is_active is False

    async def test_dispenser_detail_includes_meters(self, client,
                                                     dispenser_with_hoses, db):
        """GET /dispensers/{id} should include mechanical_meters."""
        grade = await db.get(Grade, 1)
        m = MechanicalMeter(
            dispenser_id=dispenser_with_hoses.dispenser_id,
            name="Detail Meter", meter_type="PRODUCT",
            grade_id=grade.grade_id, sort_order=1,
        )
        db.add(m)
        await db.commit()

        resp = await client.get(
            f"/api/admin/dispensers/{dispenser_with_hoses.dispenser_id}",
            headers=_admin_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "mechanical_meters" in data
        assert len(data["mechanical_meters"]) >= 1
        assert data["mechanical_meters"][0]["name"] == "Detail Meter"

    # ── POS permission check ──────────────────────────────────

    async def test_pos_user_cannot_create_meter(self, client,
                                                  dispenser_with_hoses):
        """POS dispatchers cannot access admin meter endpoints."""
        resp = await client.post(
            f"/api/admin/dispensers/{dispenser_with_hoses.dispenser_id}/meters",
            headers=_dispatcher_headers(),
            json={"name": "Hack", "meter_type": "PRODUCT", "grade_id": 1},
        )
        assert resp.status_code in (401, 403)


# ── Shift + Meter Readings Tests ───────────────────────────────────


class TestShiftMeterReadings:
    """Test meter readings during shift open/close."""

    async def test_open_shift_with_meter_readings(self, client, db):
        """Open shift with opening meter readings."""
        grade = await db.get(Grade, 1)
        d_res = await db.execute(select(Dispenser).where(Dispenser.is_active == True).limit(1))
        disp = d_res.scalar_one()

        m = MechanicalMeter(
            dispenser_id=disp.dispenser_id,
            name="Test Meter Shift", meter_type="PRODUCT",
            grade_id=grade.grade_id, sort_order=1,
        )
        db.add(m)
        await db.commit()
        await db.refresh(m)

        resp = await client.post(
            "/api/pos/shifts/open",
            headers=_dispatcher_headers(),
            json={
                "opening_cash": 0,
                "meter_readings": [
                    {"meter_id": m.meter_id, "reading_value": "12345.67"},
                ],
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["status"] == "OPEN"
        shift_id = resp.json()["shift_id"]

        # Verify readings were saved
        readings_resp = await client.get(
            f"/api/pos/shifts/{shift_id}/meter-readings",
            headers=_dispatcher_headers(),
        )
        assert readings_resp.status_code == 200
        data = readings_resp.json()
        assert len(data["meters"]) >= 1

        # Find our meter in the response
        our_meter = next(
            (m2 for m2 in data["meters"] if m2["meter_id"] == m.meter_id), None
        )
        assert our_meter is not None
        assert float(our_meter["opening_reading"]) == 12345.67
        assert our_meter["closing_reading"] is None  # not yet closed

        # Clean up: close the shift
        await client.post(
            f"/api/pos/shifts/{shift_id}/close",
            headers=_dispatcher_headers(),
            json={"notes": "test cleanup"},
        )

    async def test_close_shift_with_meter_readings(self, client, db):
        """Close shift with closing meter readings, verify differences."""
        grade = await db.get(Grade, 1)
        d_res = await db.execute(select(Dispenser).where(Dispenser.is_active == True).limit(1))
        disp = d_res.scalar_one()

        m = MechanicalMeter(
            dispenser_id=disp.dispenser_id,
            name="Close Test Meter", meter_type="PRODUCT",
            grade_id=grade.grade_id, sort_order=1,
        )
        db.add(m)
        await db.commit()
        await db.refresh(m)

        # Open with opening reading
        open_resp = await client.post(
            "/api/pos/shifts/open",
            headers=_dispatcher_headers(),
            json={
                "opening_cash": 0,
                "meter_readings": [
                    {"meter_id": m.meter_id, "reading_value": "100.00"},
                ],
            },
        )
        assert open_resp.status_code == 201
        shift_id = open_resp.json()["shift_id"]

        # Close with closing reading
        close_resp = await client.post(
            f"/api/pos/shifts/{shift_id}/close",
            headers=_dispatcher_headers(),
            json={
                "meter_readings": [
                    {"meter_id": m.meter_id, "reading_value": "250.50"},
                ],
            },
        )
        assert close_resp.status_code == 200
        data = close_resp.json()

        # Verify meter readings in close response
        assert "meter_readings" in data
        our_meter = next(
            (m2 for m2 in data["meter_readings"] if m2["meter_id"] == m.meter_id), None
        )
        assert our_meter is not None
        assert float(our_meter["opening_reading"]) == 100.00
        assert float(our_meter["closing_reading"]) == 250.50
        assert float(our_meter["difference"]) == 150.50

    async def test_shift_meter_readings_endpoint(self, client, db):
        """GET /shifts/{id}/meter-readings returns full paired data."""
        grade = await db.get(Grade, 1)
        d_res = await db.execute(select(Dispenser).where(Dispenser.is_active == True).limit(1))
        disp = d_res.scalar_one()

        m = MechanicalMeter(
            dispenser_id=disp.dispenser_id,
            name="PairedTest", meter_type="PRODUCT",
            grade_id=grade.grade_id, sort_order=1,
        )
        db.add(m)
        await db.commit()
        await db.refresh(m)

        open_resp = await client.post(
            "/api/pos/shifts/open",
            headers=_dispatcher_headers(),
            json={
                "opening_cash": 0,
                "meter_readings": [
                    {"meter_id": m.meter_id, "reading_value": "500.00"},
                ],
            },
        )
        shift_id = open_resp.json()["shift_id"]

        close_resp = await client.post(
            f"/api/pos/shifts/{shift_id}/close",
            headers=_dispatcher_headers(),
            json={
                "meter_readings": [
                    {"meter_id": m.meter_id, "reading_value": "750.00"},
                ],
            },
        )
        assert close_resp.status_code == 200

        # Now read via dedicated endpoint
        resp = await client.get(
            f"/api/pos/shifts/{shift_id}/meter-readings",
            headers=_dispatcher_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["shift_id"] == shift_id
        our = next((m2 for m2 in data["meters"] if m2["meter_id"] == m.meter_id), None)
        assert our is not None
        assert float(our["opening_reading"]) == 500.00
        assert float(our["closing_reading"]) == 750.00
        assert float(our["difference"]) == 250.00

    async def test_receipt_data_includes_meters(self, client, db):
        """GET /shifts/{id}/receipt-data includes meter readings."""
        grade = await db.get(Grade, 1)
        d_res = await db.execute(select(Dispenser).where(Dispenser.is_active == True).limit(1))
        disp = d_res.scalar_one()

        m = MechanicalMeter(
            dispenser_id=disp.dispenser_id,
            name="ReceiptTest", meter_type="PRODUCT",
            grade_id=grade.grade_id, sort_order=1,
        )
        db.add(m)
        await db.commit()
        await db.refresh(m)

        open_resp = await client.post(
            "/api/pos/shifts/open",
            headers=_dispatcher_headers(),
            json={
                "opening_cash": 0,
                "meter_readings": [
                    {"meter_id": m.meter_id, "reading_value": "0.00"},
                ],
            },
        )
        shift_id = open_resp.json()["shift_id"]

        close_resp = await client.post(
            f"/api/pos/shifts/{shift_id}/close",
            headers=_dispatcher_headers(),
            json={
                "meter_readings": [
                    {"meter_id": m.meter_id, "reading_value": "100.00"},
                ],
            },
        )
        assert close_resp.status_code == 200

        resp = await client.get(
            f"/api/pos/shifts/{shift_id}/receipt-data",
            headers=_dispatcher_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "meter_readings" in data
        our = next((m2 for m2 in data["meter_readings"] if m2["meter_id"] == m.meter_id), None)
        assert our is not None
        assert float(our["difference"]) == 100.00

    async def test_shift_open_without_readings(self, client):
        """Opening shift without meter readings is still fine (optional)."""
        resp = await client.post(
            "/api/pos/shifts/open",
            headers=_dispatcher_headers(),
            json={"opening_cash": 0},
        )
        assert resp.status_code == 201
        shift_id = resp.json()["shift_id"]

        # Close also without readings
        close_resp = await client.post(
            f"/api/pos/shifts/{shift_id}/close",
            headers=_dispatcher_headers(),
            json={},
        )
        assert close_resp.status_code == 200
        # meter_readings in response should be empty list
        assert close_resp.json()["meter_readings"] == []

    async def test_upsert_meter_reading(self, client, db):
        """Only one OPENING reading per meter per shift — uniqueness enforced."""
        grade = await db.get(Grade, 1)
        d_res = await db.execute(select(Dispenser).where(Dispenser.is_active == True).limit(1))
        disp = d_res.scalar_one()

        m = MechanicalMeter(
            dispenser_id=disp.dispenser_id, name="UpsertTest",
            meter_type="PRODUCT", grade_id=grade.grade_id, sort_order=1,
        )
        db.add(m)
        await db.commit()

        # Open shift with reading
        open_resp = await client.post(
            "/api/pos/shifts/open",
            headers=_dispatcher_headers(),
            json={
                "opening_cash": 0,
                "meter_readings": [
                    {"meter_id": m.meter_id, "reading_value": "111.11"},
                ],
            },
        )
        shift_id = open_resp.json()["shift_id"]

        # Verify only one OPENING reading exists
        result = await db.execute(
            select(MeterReading).where(
                MeterReading.meter_id == m.meter_id,
                MeterReading.shift_id == shift_id,
                MeterReading.reading_type == "OPENING",
            )
        )
        readings = result.scalars().all()
        assert len(readings) == 1
        assert float(readings[0].reading_value) == 111.11

        # Clean up
        await client.post(
            f"/api/pos/shifts/{shift_id}/close",
            headers=_dispatcher_headers(),
            json={"meter_readings": [{"meter_id": m.meter_id, "reading_value": "222.22"}]},
        )

    async def test_config_includes_meters(self, client, db):
        """GET /api/pos/config includes mechanical_meters per dispenser."""
        grade = await db.get(Grade, 1)
        d_res = await db.execute(select(Dispenser).where(Dispenser.is_active == True).limit(1))
        disp = d_res.scalar_one()

        m = MechanicalMeter(
            dispenser_id=disp.dispenser_id, name="ConfigTest",
            meter_type="PRODUCT", grade_id=grade.grade_id, sort_order=1,
        )
        db.add(m)
        await db.commit()

        resp = await client.get(
            "/api/pos/config",
            headers=_dispatcher_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "dispensers" in data

        # Find our dispenser
        our_disp = next(
            (d for d in data["dispensers"] if d["dispenser_id"] == disp.dispenser_id),
            None
        )
        assert our_disp is not None
        assert "mechanical_meters" in our_disp
        meter_names = [m2["name"] for m2 in our_disp["mechanical_meters"]]
        assert "ConfigTest" in meter_names
