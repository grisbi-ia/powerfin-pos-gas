"""API tests: identification gate — the POS must re-ask the customer's cédula.

Covers the production incident of 2026-09-13: 7 invoices lost because Key49
rejected cédulas with a bad check digit ("Invalid identification for type 05")
*after* the fuel was dispensed and paid for.

The gate has three parts:
  1. `GET /api/pos/persons/lookup` and `POST /api/pos/customers` refuse an
     invalid identification (422) — it is never stored.
  2. `POST /api/pos/dispatches` refuses a customer without a validated
     identification (cleared = NULL) or with an invalid one.
  3. `POST /api/pos/dispatches/{order}/collect` re-checks before invoicing.
  4. `PUT /api/pos/persons/{id}` is the re-capture path used after the
     dispatcher asks the customer again.
"""

import json
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.models.person import Person

# Real cédulas from production
VALID_CEDULA = "0912345675"       # seeded "Juan Carlos Pérez"
INVALID_CEDULA = "1708860005"     # EDGAR GALLAS — rejected by Key49 on 2026-09-13
ANOTHER_VALID_CEDULA = "0101644193"

DISPATCH_BODY = {
    "dispenser_id": 1, "hose_id": 1, "side": "A",
    "preset_type": "MONEY", "preset_value": "10.00",
    "unit_price": 3.103, "payment_method_id": 1,
    "dispatch_type_code": "SALE",
    "items": [{"product_id": 1, "quantity": 1, "unit_price": 3.103, "tax_rate": 0}],
}


async def _open_shift(client, auth_headers):
    await client.post("/api/pos/shifts/open", headers=auth_headers, json={
        "opening_cash": 0, "user_name": "Carlos Sarmiento"
    })


async def _get_person(db, person_id: int) -> Person:
    return (await db.execute(
        select(Person).where(Person.person_id == person_id)
    )).scalar_one()


class TestLookupRejectsInvalidIdentification:
    async def test_lookup_invalid_cedula_is_422(self, client, auth_headers):
        r = await client.get(
            "/api/pos/persons/lookup",
            params={"id_type": "CED", "id_number": INVALID_CEDULA},
            headers=auth_headers,
        )
        assert r.status_code == 422
        assert "dígito verificador" in r.json()["detail"]

    async def test_lookup_invalid_cedula_is_422_even_when_registered(
        self, client, auth_headers, db
    ):
        """A customer registered with a bad cédula (legacy data) is refused too."""
        person = await _get_person(db, 1)
        person.id_number = INVALID_CEDULA
        await db.commit()

        r = await client.get(
            "/api/pos/persons/lookup",
            params={"id_type": "CED", "id_number": INVALID_CEDULA},
            headers=auth_headers,
        )
        assert r.status_code == 422

    async def test_lookup_non_numeric_ruc_is_422(self, client, auth_headers):
        r = await client.get(
            "/api/pos/persons/lookup",
            params={"id_type": "RUC", "id_number": "GADPAUTE"},
            headers=auth_headers,
        )
        assert r.status_code == 422
        assert "solo números" in r.json()["detail"]

    async def test_lookup_normalizes_separators(self, client, auth_headers):
        """'091-234 5675' must resolve to the seeded person (local hit)."""
        r = await client.get(
            "/api/pos/persons/lookup",
            params={"id_type": "CED", "id_number": "091-234 5675"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["found"] is True
        assert r.json()["data"]["name"] == "Juan Carlos Pérez"

    async def test_lookup_reports_external_failure(self, client, auth_headers, monkeypatch):
        """A valid but unknown cédula whose provider is down says so explicitly."""
        from app.services.identity_service import IdentityProviderError

        async def _boom(id_type, id_number):
            raise IdentityProviderError("Sercobaco caído")

        monkeypatch.setattr("app.api.persons.lookup_person", _boom)

        r = await client.get(
            "/api/pos/persons/lookup",
            params={"id_type": "CED", "id_number": ANOTHER_VALID_CEDULA},
            headers=auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["found"] is False
        assert body["external_lookup_failed"] is True
        assert "No se pudo verificar" in body["warning"]

    async def test_lookup_blocks_identifier_unknown_to_the_registry(
        self, client, auth_headers, monkeypatch
    ):
        """A RUC the SRI does not know must NOT fall through to manual capture.

        Key49 rejects those with "Invalid identification for type 04" — the
        document is lost. Distinguishing it from a provider outage is the whole
        point: it is a verdict, not an outage.
        """
        from app.services.identity_service import IdentityNotFoundError

        async def _not_found(id_type, id_number):
            raise IdentityNotFoundError("RUC no encontrado en SRI")

        monkeypatch.setattr("app.api.persons.lookup_person", _not_found)

        r = await client.get(
            "/api/pos/persons/lookup",
            params={"id_type": "RUC", "id_number": "1794062180001"},
            headers=auth_headers,
        )
        assert r.status_code == 422
        assert "identificación inexistente" in r.json()["detail"]


class TestCreateCustomerValidation:
    async def test_invalid_cedula_is_not_stored(self, client, auth_headers, db):
        r = await client.post("/api/pos/customers", headers=auth_headers, json={
            "id_type": "CED", "id_number": INVALID_CEDULA, "name": "Edgar Gallas",
        })
        assert r.status_code == 422
        stored = (await db.execute(
            select(Person).where(Person.id_number == INVALID_CEDULA)
        )).scalar_one_or_none()
        assert stored is None


class TestDispatchGate:
    async def test_sale_with_cleared_identification_is_rejected(
        self, client, auth_headers, db
    ):
        """The dispatcher is forced to re-capture before the fuel flows."""
        await _open_shift(client, auth_headers)
        person = await _get_person(db, 1)
        person.id_number = None
        await db.commit()

        r = await client.post("/api/pos/dispatches", headers=auth_headers,
                              json={**DISPATCH_BODY, "person_id": person.person_id})
        assert r.status_code == 422
        assert "no tiene identificación registrada" in r.json()["detail"]

    async def test_sale_with_plate_of_unidentified_owner_is_rejected(
        self, client, auth_headers, db
    ):
        """Same gate when the customer comes from the plate owner."""
        await _open_shift(client, auth_headers)
        person = await _get_person(db, 1)
        person.id_number = None
        await db.commit()

        r = await client.post("/api/pos/dispatches", headers=auth_headers,
                              json={**DISPATCH_BODY, "plate": "ABC1234"})
        assert r.status_code == 422
        assert "no tiene identificación registrada" in r.json()["detail"]

    async def test_sale_with_invalid_identification_is_rejected(
        self, client, auth_headers, db
    ):
        await _open_shift(client, auth_headers)
        person = await _get_person(db, 1)
        person.id_number = INVALID_CEDULA
        await db.commit()

        r = await client.post("/api/pos/dispatches", headers=auth_headers,
                              json={**DISPATCH_BODY, "customer_id": INVALID_CEDULA})
        assert r.status_code == 422
        assert "Identificación inválida" in r.json()["detail"]

    async def test_calibration_without_customer_still_allowed(self, client, auth_headers):
        """requires_customer=false must keep working anonymously."""
        await _open_shift(client, auth_headers)
        r = await client.post("/api/pos/dispatches", headers=auth_headers, json={
            **DISPATCH_BODY,
            "dispatch_type_code": "CALIBRATION",
            "plate": "ZZZ1111",
        })
        assert r.status_code == 201

    async def test_collect_rechecks_identification(
        self, client, auth_headers, db, monkeypatch
    ):
        """Identification cleared after the dispatch was created blocks collect."""
        await _open_shift(client, auth_headers)
        r = await client.post("/api/pos/dispatches", headers=auth_headers,
                              json={**DISPATCH_BODY, "customer_id": VALID_CEDULA})
        assert r.status_code == 201
        order_id = r.json()["order_id"]

        # Force the dispatch into COMPLETED with a real amount
        from app.models.dispatch import Dispatch
        dispatch = (await db.execute(
            select(Dispatch).where(Dispatch.order_id == order_id)
        )).scalar_one()
        dispatch.status = "COMPLETED"
        dispatch.total = 10.00
        person = await _get_person(db, 1)
        person.id_number = None
        await db.commit()

        r = await client.post(f"/api/pos/dispatches/{order_id}/collect",
                              headers=auth_headers,
                              json={"payment_method_id": 1, "collected_amount": 10.00,
                                    "collected_by_shift_id": dispatch.shift_id})
        assert r.status_code == 422
        assert "no tiene identificación registrada" in r.json()["detail"]


class TestRecaptureIdentification:
    """PUT /api/pos/persons/{id} — the dispatcher asks the customer again."""

    async def test_recapture_valid_cedula(self, client, auth_headers, db):
        person = await _get_person(db, 1)
        person.id_number = None
        await db.commit()

        r = await client.put(f"/api/pos/persons/{person.person_id}",
                             headers=auth_headers,
                             json={"id_type": "CED", "id_number": ANOTHER_VALID_CEDULA})
        assert r.status_code == 200
        assert r.json()["id_number"] == ANOTHER_VALID_CEDULA

        db.expire_all()
        assert (await _get_person(db, 1)).id_number == ANOTHER_VALID_CEDULA

    async def test_recapture_rejects_invalid_cedula(self, client, auth_headers, db):
        person = await _get_person(db, 1)
        person.id_number = None
        await db.commit()

        r = await client.put(f"/api/pos/persons/{person.person_id}",
                             headers=auth_headers,
                             json={"id_type": "CED", "id_number": INVALID_CEDULA})
        assert r.status_code == 422
        assert "dígito verificador" in r.json()["detail"]

        db.expire_all()
        assert (await _get_person(db, 1)).id_number is None  # untouched

    async def test_recapture_rejects_duplicate(self, client, auth_headers, db):
        person1 = await _get_person(db, 1)
        person1.id_number = None
        await db.commit()

        # person 2 holds 1790012345001
        r = await client.put(f"/api/pos/persons/{person1.person_id}",
                             headers=auth_headers,
                             json={"id_type": "RUC", "id_number": "1790012345001"})
        assert r.status_code == 409
        assert "ya está registrada" in r.json()["detail"]

    async def test_recapture_unblocks_the_sale(self, client, auth_headers, db):
        """End to end: cleared ID → sale blocked → re-capture → sale works."""
        await _open_shift(client, auth_headers)
        person = await _get_person(db, 1)
        person.id_number = None
        await db.commit()

        r = await client.post("/api/pos/dispatches", headers=auth_headers,
                              json={**DISPATCH_BODY, "person_id": person.person_id})
        assert r.status_code == 422

        r = await client.put(f"/api/pos/persons/{person.person_id}",
                             headers=auth_headers,
                             json={"id_type": "CED", "id_number": ANOTHER_VALID_CEDULA})
        assert r.status_code == 200

        r = await client.post("/api/pos/dispatches", headers=auth_headers,
                              json={**DISPATCH_BODY, "person_id": person.person_id,
                                    "customer_id": ANOTHER_VALID_CEDULA})
        assert r.status_code == 201
