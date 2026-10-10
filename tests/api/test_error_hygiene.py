from fastapi.testclient import TestClient

from app.api.v1 import inspect as inspect_api
from app.main import app

client = TestClient(app)


def test_unexpected_value_error_does_not_leak_internal_details(monkeypatch) -> None:
    def fail_processing(*args, **kwargs):
        raise ValueError("PRIVATE_PARSER_TRACE_123")

    monkeypatch.setattr(inspect_api, "_process_document", fail_processing)
    response = client.post(
        "/api/v1/inspect",
        files={"file": ("draft.pdf", b"%PDF-1.4\nminimal test")},
    )

    assert response.status_code == 500
    assert "PRIVATE_PARSER_TRACE_123" not in response.text
    assert "پردازش فایل" in response.text


def test_inspection_response_is_not_cacheable() -> None:
    response = client.post(
        "/api/v1/inspect",
        files={"file": ("unsupported.txt", b"nothing")},
    )

    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["x-content-type-options"] == "nosniff"
