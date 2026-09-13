"""Unit tests: Ecuadorian identification validation.

The vectors are REAL identifications taken from production, not invented:

* `_SRI_ACCEPTED_CEDULAS` — cédulas that the SRI already authorized (any false
  negative here would mean blocking a paying customer).
* `_SRI_REJECTED_CEDULAS` — the cédulas that Key49 rejected on 2026-09-13 with
  "Invalid identification for type 05" (must never pass again).
* `_SRI_ACCEPTED_JURIDICA_RUCS` — juridical RUCs that invoice normally today
  **and fail the published module-11 check digit**. They prove the RUC check
  digit must not be blocking (see `id_validation` module docstring).
"""

import pytest

from app.services.id_validation import (
    CEDULA_LENGTH,
    RUC_LENGTH,
    _mod10,
    cedula_error,
    is_valid_cedula,
    is_valid_ruc,
    needs_registry_check,
    normalize_id_number,
    ruc_error,
    validate_identification,
)

# Cédulas the SRI already accepted (one per province).
_SRI_ACCEPTED_CEDULAS = [
    "0101644193", "0105182513", "0106177454", "0104079983", "0101877942",
    "0201522679", "0200893006", "0201689247", "0200145720", "0201459930",
    "0301086005", "0302112859", "0302611918", "0301851945", "0300851714",
    "0900600206", "0901126763", "0901259390",
]

# The 6 customers that failed invoicing on 2026-09-13 (bad check digit).
_SRI_REJECTED_CEDULAS = [
    "0102126197",  # ROMUALDO ONCE
    "0101867561",  # FERNANDO VASCONEZ
    "0104888555",  # CARLOS CARDENAS
    "1706248010",  # CARLOS MALES
    "0106190486",  # HILDA MALDONADA
    "1708860005",  # EDGAR GALLAS
]

# Juridical RUCs the SRI confirms AND that invoice today, but that fail the
# published module-11 rule → blocking on the checksum would reject them.
_SRI_ACCEPTED_JURIDICA_RUCS = [
    "1793200847001",  # CLICK SOLUCIONES S.A.S.
    "0391035013001",  # AQUASUR-TECNOLOGY S.A.S.
    "1793199902001",  # OSMO HEALTH TECHNOLOGIES S.A.S.
    "0195128571001",  # COMERCIALIZADORA VICOR S.A.S.
    "0391034503001",  # MIM CONSTRUFERRETERIA E IMPORTADORA S.A.S.
]

# Natural-person RUCs accepted by the SRI (cédula + 001).
_SRI_ACCEPTED_NATURAL_RUCS = [
    "0100086875001", "0100092741001", "0100106582001", "0100190073001",
]

# RUCs the SRI registry does NOT know (rejected by Key49 with type 04) and
# that pass the local structure rules → only the registry can reject them.
_SRI_UNKNOWN_RUCS = [
    "1794062180001",  # INLOGTRANS S.A
    "0194125200001",  # Distribuidora Urgiles
]

# RUCs the SRI registry does NOT know but that local validation ALREADY
# catches (natural RUC with a bad cédula part, bad province, bad third digit).
_SRI_UNKNOWN_RUCS_CAUGHT_LOCALLY = {
    "0103203404001": "dígito verificador",  # ISRAEL DURAN
    "0104464999001": "dígito verificador",  # MARIA BANEGAS
    "2612250067001": "provincia",           # Juan pablo terrado
    "0984761739001": "tercer dígito",       # Nora mary dueña
    "GADPAUTE": "solo números",
}


class TestCedula:
    @pytest.mark.parametrize("cedula", _SRI_ACCEPTED_CEDULAS)
    def test_accepts_every_sri_accepted_cedula(self, cedula):
        assert is_valid_cedula(cedula) is True
        assert cedula_error(cedula) is None

    @pytest.mark.parametrize("cedula", _SRI_REJECTED_CEDULAS)
    def test_rejects_every_cedula_key49_rejected(self, cedula):
        assert is_valid_cedula(cedula) is False
        assert "dígito verificador" in cedula_error(cedula)

    def test_normalizes_separators_and_case(self):
        assert normalize_id_number(" 010-164.4193 ") == "0101644193"
        assert is_valid_cedula("010-164 4193") is True

    def test_rejects_empty(self):
        assert cedula_error("") == "Ingrese el número de cédula."
        assert cedula_error(None) == "Ingrese el número de cédula."

    def test_rejects_non_numeric(self):
        assert "solo números" in cedula_error("01016441AB")

    def test_rejects_wrong_length(self):
        assert str(CEDULA_LENGTH) in cedula_error("010164419")
        assert str(CEDULA_LENGTH) in cedula_error("01016441931")

    def test_rejects_invalid_province(self):
        # 00 and 25+ (except 30) are not provinces.
        assert "provincia" in cedula_error("0001644193")
        assert "provincia" in cedula_error("9901644193")

    def test_accepts_province_30(self):
        """30 = exterior. Build a valid cédula for that province on the fly."""
        body = "304000080"
        candidate = body + str(_mod10(body))
        assert is_valid_cedula(candidate) is True


class TestRuc:
    @pytest.mark.parametrize("ruc", _SRI_ACCEPTED_JURIDICA_RUCS)
    def test_does_not_block_real_juridica_rucs(self, ruc):
        """The published module-11 fails on these — they must still pass."""
        assert is_valid_ruc(ruc) is True
        assert ruc_error(ruc) is None

    @pytest.mark.parametrize("ruc", _SRI_ACCEPTED_NATURAL_RUCS)
    def test_accepts_natural_rucs(self, ruc):
        assert is_valid_ruc(ruc) is True

    def test_rejects_natural_ruc_with_bad_cedula_part(self):
        # 1708860005 (EDGAR GALLAS) is an invalid cédula → its RUC is invalid.
        assert is_valid_ruc("1708860005001") is False
        assert "dígito verificador" in ruc_error("1708860005001")

    @pytest.mark.parametrize("ruc", _SRI_UNKNOWN_RUCS)
    def test_structure_valid_but_registry_unknown(self, ruc):
        """Structure cannot decide these: the SRI registry must be consulted."""
        assert is_valid_ruc(ruc) is True
        assert needs_registry_check("RUC", ruc) is True

    @pytest.mark.parametrize("ruc,expected", _SRI_UNKNOWN_RUCS_CAUGHT_LOCALLY.items())
    def test_unknown_rucs_already_caught_locally(self, ruc, expected):
        """15 of the 16 invalid RUCs found in production never reach the API."""
        assert is_valid_ruc(ruc) is False
        assert expected in ruc_error(ruc)

    def test_rejects_wrong_length(self):
        assert str(RUC_LENGTH) in ruc_error("179320084700")
        assert str(RUC_LENGTH) in ruc_error("17932008470011")

    def test_rejects_non_numeric(self):
        assert "solo números" in ruc_error("GADPAUTE")

    def test_rejects_invalid_province(self):
        assert "provincia" in ruc_error("9993200847001")

    def test_rejects_invalid_third_digit(self):
        assert "tercer dígito" in ruc_error("1783200847001")

    def test_rejects_missing_001_suffix(self):
        assert "001" in ruc_error("1793200847002")

    def test_empty(self):
        assert ruc_error("") == "Ingrese el número de RUC."
        assert ruc_error(None) == "Ingrese el número de RUC."


class TestValidateIdentification:
    def test_dispatches_by_type(self):
        assert validate_identification("CED", "0101644193") is None
        assert validate_identification("CED", "0102126197") is not None
        assert validate_identification("RUC", "1793200847001") is None
        assert validate_identification("RUC", "GADPAUTE") is not None

    def test_type_is_case_insensitive(self):
        assert validate_identification("ced", "0101644193") is None

    def test_unsupported_type(self):
        assert "no soportado" in validate_identification("PASAPORTE", "123")

    def test_registry_check_only_for_ruc(self):
        assert needs_registry_check("RUC", "0100086875001") is True
        assert needs_registry_check("CED", "0101644193") is False
        assert needs_registry_check("ced", "0101644193") is False
