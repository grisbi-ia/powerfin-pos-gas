"""Unit tests: capture Key49 error responses in sri_messages.

History: a production incident where Key49 returned HTTP 402 with body
{"error": {"code": "PLAN_EXPIRED", "message": "Plan expirado"}} — but the
backend stored only "Key49 HTTP 402", hiding the real cause for days.
These tests lock in that code + message (+ validation details) are captured.
"""

from app.services.key49_service import _key49_error_message


class _FakeResponse:
    def __init__(self, status_code: int, body, text: str | None = None):
        self.status_code = status_code
        self._body = body
        self.text = text if text is not None else str(body)

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class TestKey49ErrorMessage:
    def test_captures_plan_expired(self):
        resp = _FakeResponse(402, {"error": {"code": "PLAN_EXPIRED", "message": "Plan expirado"}})
        assert _key49_error_message(resp) == "Key49 HTTP 402: PLAN_EXPIRED — Plan expirado"

    def test_captures_validation_details(self):
        resp = _FakeResponse(400, {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request contains invalid fields",
                "details": [
                    {"field": "recipient.id", "message": "RUC debe tener 13 dígitos"},
                    {"field": "items", "message": "At least one item is required"},
                ],
            }
        })
        msg = _key49_error_message(resp)
        assert msg.startswith("Key49 HTTP 400: VALIDATION_ERROR")
        assert "RUC debe tener 13 dígitos" in msg
        assert "At least one item is required" in msg

    def test_code_only(self):
        resp = _FakeResponse(500, {"error": {"code": "INTERNAL"}})
        assert _key49_error_message(resp) == "Key49 HTTP 500: INTERNAL"

    def test_unparseable_body_falls_back_to_text(self):
        resp = _FakeResponse(502, ValueError("boom"), text="<html>bad gateway</html>")
        assert _key49_error_message(resp) == "Key49 HTTP 502: <html>bad gateway</html>"

    def test_non_standard_body_is_included(self):
        resp = _FakeResponse(418, {"detail": "teapot"})
        assert "Key49 HTTP 418" in _key49_error_message(resp)
        assert "teapot" in _key49_error_message(resp)

    def test_message_is_capped_at_500_chars(self):
        """sri_messages column is String(500) — never overflow it."""
        resp = _FakeResponse(400, {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "x" * 800,
            }
        })
        assert len(_key49_error_message(resp)) <= 500
