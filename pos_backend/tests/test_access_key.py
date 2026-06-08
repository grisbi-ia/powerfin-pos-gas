"""Tests for SRI access key generation."""

import pytest
from datetime import date
from app.services.access_key_service import generate_access_key, _modulo_11, DOC_TYPE_CODES


class TestAccessKey:
    """Test the 49-digit SRI access key generator."""

    def test_generates_49_digits(self):
        key = generate_access_key(
            emission_date=date(2026, 6, 8),
            doc_type="FACTURA",
            ruc="0190379760001",
            sri_environment=2,
            establishment="001",
            emission_point="004",
            sequential=18,
            emission_type=1,
        )
        assert len(key) == 49
        assert key.isdigit()

    def test_date_format_ddmmaaaa(self):
        key = generate_access_key(
            emission_date=date(2026, 6, 8),
            doc_type="FACTURA",
            ruc="0190379760001",
            sri_environment=2,
            establishment="001",
            emission_point="004",
            sequential=18,
            emission_type=1,
        )
        assert key[:8] == "08062026"

    def test_tipo_comprobante_factura(self):
        key = generate_access_key(
            emission_date=date(2026, 6, 8),
            doc_type="FACTURA",
            ruc="0190379760001",
            sri_environment=2,
            establishment="001",
            emission_point="004",
            sequential=18,
            emission_type=1,
        )
        assert key[8:10] == "01"

    def test_ruc_13_digits(self):
        key = generate_access_key(
            emission_date=date(2026, 6, 8),
            doc_type="FACTURA",
            ruc="0190379760001",
            sri_environment=2,
            establishment="001",
            emission_point="004",
            sequential=18,
            emission_type=1,
        )
        assert key[10:23] == "0190379760001"

    def test_ambiente_1_digit_produccion(self):
        """Ambiente is 1 digit: 1=Pruebas, 2=Produccion."""
        key = generate_access_key(
            emission_date=date(2026, 6, 8),
            doc_type="FACTURA",
            ruc="0190379760001",
            sri_environment=2,
            establishment="001",
            emission_point="004",
            sequential=18,
            emission_type=1,
        )
        # Position 23 (0-indexed) = ambiente, 1 digit
        assert key[23] == "2"

    def test_ambiente_1_digit_pruebas(self):
        key = generate_access_key(
            emission_date=date(2026, 6, 8),
            doc_type="FACTURA",
            ruc="0190379760001",
            sri_environment=1,
            establishment="001",
            emission_point="004",
            sequential=18,
            emission_type=1,
        )
        assert key[23] == "1"

    def test_establecimiento(self):
        key = generate_access_key(
            emission_date=date(2026, 6, 8),
            doc_type="FACTURA",
            ruc="0190379760001",
            sri_environment=2,
            establishment="001",
            emission_point="004",
            sequential=18,
            emission_type=1,
        )
        # Positions 24-27 (0-indexed: 24:27)
        assert key[24:27] == "001"

    def test_punto_emision(self):
        key = generate_access_key(
            emission_date=date(2026, 6, 8),
            doc_type="FACTURA",
            ruc="0190379760001",
            sri_environment=2,
            establishment="001",
            emission_point="004",
            sequential=18,
            emission_type=1,
        )
        # Positions 27-30 (0-indexed: 27:30)
        assert key[27:30] == "004"

    def test_secuencial_9_digits(self):
        key = generate_access_key(
            emission_date=date(2026, 6, 8),
            doc_type="FACTURA",
            ruc="0190379760001",
            sri_environment=2,
            establishment="001",
            emission_point="004",
            sequential=18,
            emission_type=1,
        )
        # Positions 30-39 (0-indexed: 30:39)
        assert key[30:39] == "000000018"

    def test_codigo_numerico_8_digits(self):
        key = generate_access_key(
            emission_date=date(2026, 6, 8),
            doc_type="FACTURA",
            ruc="0190379760001",
            sri_environment=2,
            establishment="001",
            emission_point="004",
            sequential=18,
            emission_type=1,
        )
        # Positions 39-47 (0-indexed: 39:47)
        assert key[39:47] == "00000018"

    def test_tipo_emision_at_position_47(self):
        """Tipo de Emision is at position 47 (0-indexed), 1 digit."""
        key = generate_access_key(
            emission_date=date(2026, 6, 8),
            doc_type="FACTURA",
            ruc="0190379760001",
            sri_environment=2,
            establishment="001",
            emission_point="004",
            sequential=18,
            emission_type=1,
        )
        assert key[47] == "1"

    def test_verificador_at_position_48(self):
        key = generate_access_key(
            emission_date=date(2026, 6, 8),
            doc_type="FACTURA",
            ruc="0190379760001",
            sri_environment=2,
            establishment="001",
            emission_point="004",
            sequential=18,
            emission_type=1,
        )
        verificador = int(key[48])
        assert 0 <= verificador <= 9

    def test_full_structure(self):
        """Verify the complete structure matches SRI spec."""
        key = generate_access_key(
            emission_date=date(2026, 6, 8),
            doc_type="FACTURA",
            ruc="0190379760001",
            sri_environment=2,
            establishment="001",
            emission_point="004",
            sequential=18,
            emission_type=1,
        )
        assert len(key) == 49
        # Verify each segment
        assert key[0:8] == "08062026"        # fecha
        assert key[8:10] == "01"             # tipo comprobante
        assert key[10:23] == "0190379760001" # ruc
        assert key[23] == "2"                # ambiente (1 digit)
        assert key[24:27] == "001"           # establecimiento
        assert key[27:30] == "004"           # punto emisión
        assert key[30:39] == "000000018"     # secuencial
        assert key[39:47] == "00000018"      # código numérico
        assert key[47] == "1"                # tipo emisión (1 digit)
        # key[48] = dígito verificador

    def test_all_doc_types(self):
        for doc_type, code in DOC_TYPE_CODES.items():
            key = generate_access_key(
                emission_date=date(2026, 6, 8),
                doc_type=doc_type,
                ruc="0190379760001",
                sri_environment=2,
                establishment="001",
                emission_point="004",
                sequential=1,
                emission_type=1,
            )
            assert key[8:10] == code

    def test_ruc_pads_to_13(self):
        key = generate_access_key(
            emission_date=date(2026, 6, 8),
            doc_type="FACTURA",
            ruc="123",
            sri_environment=2,
            establishment="001",
            emission_point="004",
            sequential=1,
            emission_type=1,
        )
        assert key[10:23] == "0000000000123"

    def test_modulo_11_known_case(self):
        result = _modulo_11("412615330000000000000000000000000000000000000000")
        assert 0 <= result <= 9

    def test_custom_codigo_numerico(self):
        key = generate_access_key(
            emission_date=date(2026, 6, 8),
            doc_type="FACTURA",
            ruc="0190379760001",
            sri_environment=2,
            establishment="001",
            emission_point="004",
            sequential=18,
            emission_type=1,
            codigo_numerico=99999999,
        )
        assert key[39:47] == "99999999"
