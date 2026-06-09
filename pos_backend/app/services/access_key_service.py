"""SRI access key generator (49-digit Clave de Acceso).

Structure (49 digits):
    01-08: Fecha DDMMAAAA
    09-10: Tipo de Comprobante (01=Factura, 04=NotaCrédito, etc.)
    11-23: RUC del emisor (13 dígitos)
    24:    Tipo de Ambiente (1=Pruebas, 2=Producción) — 1 dígito
    25-27: Establecimiento (3 dígitos)
    28-30: Punto de Emisión (3 dígitos)
    31-39: Secuencial (9 dígitos, relleno con ceros a la izquierda)
    40-47: Código Numérico (8 dígitos)
    48:    Tipo de Emisión (1=Normal) — 1 dígito
    49:    Dígito Verificador (Módulo 11)
"""

import random
from datetime import date


# Mapping from doc_type string to SRI numeric code
DOC_TYPE_CODES = {
    "FACTURA": "01",
    "NOTA_CREDITO": "04",
    "NOTA_DEBITO": "05",
    "GUIA_REMISION": "06",
    "COMPROBANTE_RETENCION": "07",
}


def _modulo_11(digits: str) -> int:
    """Compute the Módulo 11 check digit for the first 48 digits.

    Algorithm: multiply each digit from RIGHT to LEFT by weights
    2,3,4,5,6,7 (cycling), sum the products, compute 11 - (sum % 11).
    If the result is 10 or 11, return 0.
    """
    weights = [2, 3, 4, 5, 6, 7]
    total = 0
    w_idx = 0

    # Process from rightmost to leftmost (position 48 down to 1)
    for ch in reversed(digits):
        d = int(ch)
        total += d * weights[w_idx % 6]
        w_idx += 1

    remainder = total % 11
    result = 11 - remainder
    if result >= 10:
        return 0
    return result


def generate_access_key(
    emission_date: date,
    doc_type: str,
    ruc: str,
    sri_environment: int,
    establishment: str,
    emission_point: str,
    sequential: int,
    emission_type: int = 1,
    codigo_numerico: int | None = None,
) -> str:
    """Generate the 49-digit SRI access key.

    Args:
        emission_date: Date of emission (local date).
        doc_type: Document type code (e.g. "FACTURA", "NOTA_CREDITO").
        ruc: 13-digit RUC of the issuer.
        sri_environment: 1=PRUEBAS, 2=PRODUCCION.
        establishment: 3-digit establishment code (e.g. "001").
        emission_point: 3-digit emission point code (e.g. "004").
        sequential: Sequential number (integer, will be zero-padded to 9 digits).
        emission_type: 1=Normal (default).
        codigo_numerico: 8-digit numeric code. Defaults to sequential zero-padded.

    Returns:
        49-digit access key string.
    """
    # 1. Fecha (8 digits: DDMMAAAA)
    fecha = emission_date.strftime("%d%m%Y")

    # 2. Tipo de Comprobante (2 digits)
    tipo = DOC_TYPE_CODES.get(doc_type.upper(), "01")

    # 3. RUC (13 digits)
    ruc_str = ruc.strip().zfill(13)

    # 4. Ambiente (1 digit: 1=Pruebas, 2=Producción)
    ambiente = str(sri_environment)

    # 5. Establecimiento (3 digits)
    estab = establishment.strip().zfill(3)

    # 6. Punto de Emisión (3 digits)
    pto_emision = emission_point.strip().zfill(3)

    # 7. Secuencial (9 digits, zero-padded)
    secuencial = str(sequential).zfill(9)

    # 8. Código Numérico (8 digits) — random to avoid repetition
    if codigo_numerico is None:
        codigo_numerico = random.randint(0, 99999999)
    codigo = str(codigo_numerico).zfill(8)

    # 9. Tipo de Emisión (1 digit)
    tipo_emision = str(emission_type)

    # Build first 48 digits
    first_48 = (
        fecha + tipo + ruc_str + ambiente + estab
        + pto_emision + secuencial + codigo + tipo_emision
    )

    # 10. Dígito Verificador (Módulo 11)
    verificador = _modulo_11(first_48)

    return first_48 + str(verificador)
