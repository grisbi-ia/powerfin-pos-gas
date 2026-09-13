"""Ecuadorian identification validation (cédula / RUC).

Single source of truth for the check-digit rules used by the POS backend.
The frontend mirrors these rules in `pos/src/lib/utils/id-validation.ts`
(offline feedback only — the backend is always the authority).

Rule set — derived from production data, not from theory
========================================================
**Cédula (CED)** — SRI module-10 check digit, hard blocking.
    Key49 itself rejects cédulas with a bad check digit ("Invalid
    identification for type 05"), so validating here is a *pre-check of a rule
    Key49 already applies*. Measured against 3,743 identifications that the SRI
    had already accepted: **0 false negatives**. Safe to block on.

**RUC — natural person** (third digit 0-5) — cédula module-10 on the first 10
    digits + "001" suffix. Measured against the 638 natural RUCs the SRI had
    already accepted: 637/637 valid pass (the only one that fails,
    0104248314001, is also NOT FOUND in the SRI registry). Safe to block on.

**RUC — jurídica (9) / pública (6)** — structure only. The published
    module-11 check digit is **NOT reliable** and must not be enforced: the SRI
    registry contains RUCs that fail it (e.g. CLICK SOLUCIONES S.A.S.
    1793200847001 invoices normally today) and solving the linear system over
    90 SRI-confirmed juridical RUCs is mathematically **inconsistent** — no
    single weight vector fits them all. Blocking on it would reject real
    customers. Existence must be confirmed against the SRI registry instead
    (see `needs_registry_check` / `identity_service.lookup_person`).

No silent fallbacks: every function returns a definite answer, and callers
turn it into a visible error message (never a silent save).
"""

CEDULA_LENGTH = 10
RUC_LENGTH = 13

ID_TYPE_CEDULA = "CED"
ID_TYPE_RUC = "RUC"
SUPPORTED_ID_TYPES = (ID_TYPE_CEDULA, ID_TYPE_RUC)

# 01-24 = provinces; 30 = exterior / documents issued abroad.
VALID_PROVINCES = frozenset([f"{n:02d}" for n in range(1, 25)] + ["30"])

_CEDULA_WEIGHTS = (2, 1, 2, 1, 2, 1, 2, 1, 2)
_RUC_JURIDICA_WEIGHTS = (4, 3, 2, 7, 6, 5, 4, 3, 2)
_RUC_PUBLICA_WEIGHTS = (3, 2, 7, 6, 5, 4, 3, 2)

# Third digit → taxpayer kind
_RUC_NATURAL_THIRD = frozenset("012345")
_RUC_PUBLICA_THIRD = "6"
_RUC_JURIDICA_THIRD = "9"

_RUC_SUFFIX = "001"


def normalize_id_number(value: str | None) -> str:
    """Strip spaces/dashes/dots and uppercase — the POS keypad and the
    identity API both introduce separators."""
    if not value:
        return ""
    return (
        str(value)
        .strip()
        .upper()
        .replace(" ", "")
        .replace("-", "")
        .replace(".", "")
    )


def _mod10(digits: str) -> int:
    """SRI module-10 check digit (cédulas and natural-person RUCs)."""
    total = 0
    for digit, weight in zip(digits, _CEDULA_WEIGHTS):
        product = int(digit) * weight
        total += product - 9 if product > 9 else product
    return (10 - (total % 10)) % 10


def _mod11(digits: str, weights: tuple[int, ...]) -> int:
    """SRI module-11 check digit (jurídica/pública RUC — see module docstring:
    kept for structure diagnostics, never used to block)."""
    total = sum(int(d) * w for d, w in zip(digits, weights))
    check = 11 - (total % 11)
    return 0 if check == 11 else check


def is_valid_cedula(id_number: str) -> bool:
    """True when `id_number` is a structurally valid Ecuadorian cédula."""
    return cedula_error(id_number) is None


def cedula_error(id_number: str) -> str | None:
    """Return a user-facing error, or None when the cédula is valid."""
    value = normalize_id_number(id_number)

    if not value:
        return "Ingrese el número de cédula."
    if not value.isdigit():
        return "La cédula debe contener solo números."
    if len(value) != CEDULA_LENGTH:
        return f"La cédula debe tener {CEDULA_LENGTH} dígitos."
    if value[:2] not in VALID_PROVINCES:
        return (
            f"La cédula tiene un código de provincia inválido ({value[:2]}). "
            "Verifique el número con el cliente."
        )
    if _mod10(value[:9]) != int(value[9]):
        return (
            "La cédula no es válida (dígito verificador incorrecto). "
            "Vuelva a pedir el número al cliente."
        )
    return None


def is_valid_ruc(id_number: str) -> bool:
    """True when `id_number` passes the *blocking* RUC rules (structure +
    natural-person check digit). Jurídica/pública check digits are NOT part of
    this decision — see the module docstring."""
    return ruc_error(id_number) is None


def ruc_error(id_number: str) -> str | None:
    """Return a user-facing error, or None when the RUC passes the blocking
    rules. Does not check existence in the SRI registry."""
    value = normalize_id_number(id_number)

    if not value:
        return "Ingrese el número de RUC."
    if not value.isdigit():
        return "El RUC debe contener solo números (13 dígitos)."
    if len(value) != RUC_LENGTH:
        return f"El RUC debe tener {RUC_LENGTH} dígitos."
    if value[:2] not in VALID_PROVINCES:
        return (
            f"El RUC tiene un código de provincia inválido ({value[:2]}). "
            "Verifique el número con el cliente."
        )
    third = value[2]
    if third not in _RUC_NATURAL_THIRD | {_RUC_PUBLICA_THIRD, _RUC_JURIDICA_THIRD}:
        return (
            "El RUC tiene un tercer dígito inválido "
            f"({third}). Verifique el número con el cliente."
        )
    if value[-len(_RUC_SUFFIX):] != _RUC_SUFFIX:
        return "El RUC debe terminar en 001 (establecimiento matriz)."

    if third in _RUC_NATURAL_THIRD:
        # Persona natural: first 10 digits are the holder's cédula.
        ced = value[:CEDULA_LENGTH]
        error = cedula_error(ced)
        if error is not None:
            return error
    return None


def needs_registry_check(id_type: str, id_number: str) -> bool:
    """True when existence must be confirmed against the SRI registry.

    Every RUC needs it: the POS backend auto-saves whatever the SRI returns,
    and the jurídica/pública check digit cannot be trusted locally.
    """
    return (id_type or "").upper() == ID_TYPE_RUC


def validate_identification(id_type: str, id_number: str | None) -> str | None:
    """Validate any supported identification.

    Returns None when valid, otherwise a user-facing Spanish message.
    """
    normalized_type = (id_type or "").strip().upper()
    if normalized_type not in SUPPORTED_ID_TYPES:
        return "Tipo de identificación no soportado. Use CED (cédula) o RUC."

    if normalized_type == ID_TYPE_CEDULA:
        return cedula_error(id_number or "")
    return ruc_error(id_number or "")
