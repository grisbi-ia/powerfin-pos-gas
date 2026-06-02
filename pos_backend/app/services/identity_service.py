"""External identity lookup service — Sercobaco (CED) and SRI (RUC)."""

from typing import Optional

import httpx

from app.config import settings

IDENTITY_API_URL = "http://131.161.221.131:2356"
IDENTITY_API_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJnYXMiLCJ1c2VySWQiOjUsImVtYWlsIjoiZ2FzQGRhdGFnby5jb20iLCJmdWxsTmFtZSI6IlBvd2VyZmluIFBPUyBHQVMgSW50ZWdyYXRpb24iLCJyb2xlcyI6WyJBUElfQ0xJRU5UIl0sImlhdCI6MTc4MDQyODI3OSwiZXhwIjoxODExOTY0Mjc5fQ.fYSb--was6n089W-CCZUzY2vSL7qYKt1VUq_eiaYLtA"


class IdentityLookupError(Exception):
    """Raised when the identity API fails or returns no data."""


class PersonData:
    """Normalized person data from identity APIs."""

    def __init__(
        self,
        name: str,
        id_type: str,
        id_number: str,
        address: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
    ):
        self.name = name
        self.id_type = id_type
        self.id_number = id_number
        self.address = address
        self.email = email
        self.phone = phone

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "id_type": self.id_type,
            "id_number": self.id_number,
            "address": self.address,
            "email": self.email,
            "phone": self.phone,
        }


async def lookup_person(id_type: str, id_number: str) -> PersonData:
    """
    Look up a person by ID type and number using external APIs.

    Args:
        id_type: "CED" (Sercobaco) or "RUC" (SRI)
        id_number: The identification number

    Returns:
        PersonData with name, address, etc.

    Raises:
        IdentityLookupError: if the API call fails or returns no data
    """
    if id_type not in ("CED", "RUC"):
        raise IdentityLookupError(f"Tipo de documento no soportado: {id_type}")

    broker = "sercobaco" if id_type == "CED" else "sri"
    url = f"{IDENTITY_API_URL}/v1/info/ALL/{broker}/{id_number}"

    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {IDENTITY_API_TOKEN}"},
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as e:
            raise IdentityLookupError(f"Error de conexión al servicio de identidad: {e}")
        except Exception as e:
            raise IdentityLookupError(f"Error inesperado: {e}")

    if not data.get("successful"):
        msg = data.get("message", "Error desconocido")
        raise IdentityLookupError(f"Consulta fallida: {msg}")

    if id_type == "CED":
        return _parse_ced_data(data, id_number)
    else:
        return _parse_ruc_data(data, id_number)


def _parse_ced_data(data: dict, cedula: str) -> PersonData:
    """Extract person data from Sercobaco CED response."""
    inner = data.get("data", {})

    # Find the matching person data (d_datos = the searched person)
    datos = inner.get("d_datos") or inner.get("c_datos") or {}

    name = datos.get("d_nombre") or datos.get("c_nombre") or datos.get("d_razon", "")
    domicilio = datos.get("d_domicilio") or datos.get("c_domicilio", "")

    if not name:
        name = datos.get("d_razon", "")

    if not name:
        raise IdentityLookupError("No se encontraron datos para esta cédula")

    # Extract email — format: "email1||email2" → take first
    email = None
    emails_list = inner.get("d_emails") or []
    if emails_list:
        raw = emails_list[0].get("email", "")
        if raw:
            email = raw.split("||")[0].strip()

    # Extract phone — format: "0993832368||072587794" → take first
    phone = None
    phones_list = inner.get("d_telefonos") or []
    if phones_list:
        raw = phones_list[0].get("telefono", "")
        if raw:
            phone = raw.split("||")[0].strip()

    address = domicilio if domicilio else None

    return PersonData(
        name=name.strip(),
        id_type="CED",
        id_number=cedula,
        address=address,
        email=email,
        phone=phone,
    )


def _parse_ruc_data(data: dict, ruc: str) -> PersonData:
    """Extract person data from SRI RUC response."""
    inner = data.get("data", {})
    contrib = inner.get("contribuyente", {})

    name = contrib.get("razonSocial", "")
    if not name:
        raise IdentityLookupError("No se encontraron datos para este RUC")

    # Get first establishment address (prefer MATRIZ)
    establecimientos = inner.get("establecimientos", [])
    address = None
    for est in establecimientos:
        direccion = est.get("direccionCompleta", "")
        if direccion:
            address = direccion
            # Prefer the MATRIZ if available
            if est.get("matriz") == "SI":
                break

    return PersonData(
        name=name.strip(),
        id_type="RUC",
        id_number=ruc,
        address=address,
        email=None,
        phone=None,
    )
