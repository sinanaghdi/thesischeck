"""Tests for the private parser-service boundary and web-to-service client."""

from __future__ import annotations

import base64
import json
from io import BytesIO
from urllib.error import HTTPError
from urllib.request import Request

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.parsing import service as parser_service
from app.parsing import worker_client
from app.parsing.safety import DocumentValidationError
from app.schemas.document import NormalizedDocument

TEST_TOKEN = "unit-test-parser-token-that-is-long-enough-to-test"


def service_settings(token: str = TEST_TOKEN) -> Settings:
    return Settings(
        max_upload_mb=1,
        parser_service_token=token,
        parser_worker_timeout_seconds=5,
        parser_worker_cpu_seconds=2,
        parser_worker_memory_mb=256,
        parser_worker_concurrency=1,
    )


def test_parser_service_rejects_missing_or_wrong_token(monkeypatch) -> None:
    monkeypatch.setattr(parser_service, "get_settings", lambda: service_settings())
    called: list[bool] = []

    def should_not_parse(*args, **kwargs):
        called.append(True)
        raise AssertionError("parser must not run for an unauthenticated request")

    monkeypatch.setattr(parser_service, "parse_document_in_worker", should_not_parse)
    client = TestClient(parser_service.app)
    missing = client.post("/internal/parse", content=b"doc", headers={"content-type": "application/octet-stream"})
    wrong = client.post("/internal/parse", content=b"doc", headers={"content-type": "application/octet-stream", "x-parser-token": "wrong"})
    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert called == []


def test_parser_service_decodes_filename_and_returns_normalized_document(monkeypatch) -> None:
    monkeypatch.setattr(parser_service, "get_settings", lambda: service_settings())
    observed: dict[str, object] = {}
    document = NormalizedDocument(
        source_format="docx", file_name="thesis.docx", elements=[], diagnostics=[],
        parsing_complete=True, page_count=None, format_metadata={},
    )

    def fake_parse(filename, content, **kwargs):
        observed.update({"filename": filename, "content": content, **kwargs})
        return document

    monkeypatch.setattr(parser_service, "parse_document_in_worker", fake_parse)
    encoded = base64.urlsafe_b64encode(b"thesis.docx").decode("ascii")
    response = TestClient(parser_service.app).post(
        "/internal/parse", content=b"synthetic docx bytes",
        headers={"content-type": "application/octet-stream", "x-parser-token": TEST_TOKEN, "x-document-filename-b64": encoded},
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["ok"] is True
    assert response.json()["document"]["file_name"] == "thesis.docx"
    assert observed["filename"] == "thesis.docx"
    assert observed["content"] == b"synthetic docx bytes"
    assert observed["concurrency"] == 1


def test_parser_service_maps_validation_errors_to_controlled_response(monkeypatch) -> None:
    monkeypatch.setattr(parser_service, "get_settings", lambda: service_settings())

    def invalid_document(*args, **kwargs):
        raise DocumentValidationError("invalid_docx", "ساختار فایل Word معتبر نیست.")

    monkeypatch.setattr(parser_service, "parse_document_in_worker", invalid_document)
    encoded = base64.urlsafe_b64encode(b"bad.docx").decode("ascii")
    response = TestClient(parser_service.app).post(
        "/internal/parse", content=b"bad",
        headers={"content-type": "application/octet-stream", "x-parser-token": TEST_TOKEN, "x-document-filename-b64": encoded},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_docx"
    assert "Traceback" not in response.text


def test_service_client_disables_ambient_proxy_and_validates_result(monkeypatch) -> None:
    payload = json.dumps({"ok": True, "document": {
        "source_format": "docx", "file_name": "thesis.docx", "elements": [],
        "diagnostics": [], "page_count": None, "parsing_complete": True, "format_metadata": {},
    }}).encode("utf-8")
    observed: dict[str, object] = {}

    class FakeResponse:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, size: int) -> bytes:
            observed["read_size"] = size
            return payload

    class FakeOpener:
        def open(self, request: Request, timeout: int):
            observed["url"] = request.full_url
            observed["headers"] = {k.lower(): v for k, v in request.header_items()}
            observed["body"] = request.data
            observed["timeout"] = timeout
            return FakeResponse()

    def fake_build_opener(handler):
        observed["proxy_handler"] = handler
        return FakeOpener()

    monkeypatch.setattr("urllib.request.build_opener", fake_build_opener)
    parsed = worker_client.parse_document_via_service(
        r"C:\Users\student\thesis.docx", b"synthetic document",
        max_size_bytes=1024, timeout_seconds=45,
        service_url="http://parser:8001", service_token=TEST_TOKEN,
    )
    assert parsed.file_name == "thesis.docx"
    assert observed["url"] == "http://parser:8001/internal/parse"
    assert observed["body"] == b"synthetic document"
    assert observed["timeout"] == 45
    assert observed["headers"]["x-parser-token"] == TEST_TOKEN
    assert observed["proxy_handler"].proxies == {}


def test_service_client_maps_body_limit_to_file_too_large(monkeypatch) -> None:
    import pytest
    error_payload = json.dumps({"detail": {"code": "request_body_too_large", "message": "حجم درخواست زیاد است."}}).encode("utf-8")

    class FakeOpener:
        def open(self, request: Request, timeout: int):
            raise HTTPError(request.full_url, 413, "Payload too large", hdrs=None, fp=BytesIO(error_payload))

    monkeypatch.setattr("urllib.request.build_opener", lambda handler: FakeOpener())
    with pytest.raises(DocumentValidationError) as error:
        worker_client.parse_document_via_service(
            "too-large.docx", b"small", max_size_bytes=1024,
            timeout_seconds=45, service_url="http://parser:8001", service_token=TEST_TOKEN,
        )
    assert error.value.code == "file_too_large"
