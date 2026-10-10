"""Deterministic adversarial regression tests for upload and worker boundaries."""

from __future__ import annotations

import asyncio
import json
import random
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from starlette.responses import JSONResponse

from app.core.security import RequestBodyLimitMiddleware
from app.parsing import worker_client
from app.parsing.safety import DocumentValidationError, validate_document_bytes


def make_docx(*, document_xml: bytes = b"<document/>") -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


@pytest.mark.parametrize("length", [1, 7, 31, 127, 511, 1023])
def test_deterministic_random_non_archives_fail_with_controlled_errors(length: int) -> None:
    rng = random.Random(20_261_010 + length)
    payload = bytes(rng.randrange(256) for _ in range(length))

    with pytest.raises(DocumentValidationError) as error:
        validate_document_bytes("untrusted.docx", payload, max_size_bytes=2048)

    assert error.value.code == "invalid_docx"
    assert "Traceback" not in str(error.value)
    assert payload[:12].decode("latin-1") not in error.value.message


@pytest.mark.parametrize(
    ("limit", "expected_code"),
    [
        ({"max_zip_entries": 1}, "archive_entry_limit"),
        ({"max_uncompressed_bytes": 1}, "archive_too_large"),
        ({"max_single_entry_bytes": 1}, "archive_entry_too_large"),
    ],
)
def test_docx_archive_limits_fail_closed(
    limit: dict[str, int], expected_code: str
) -> None:
    with pytest.raises(DocumentValidationError) as error:
        validate_document_bytes(
            "limits.docx",
            make_docx(),
            max_size_bytes=1024 * 1024,
            **limit,
        )

    assert error.value.code == expected_code


def test_docx_with_extreme_compression_ratio_is_rejected() -> None:
    payload = make_docx(document_xml=b"A" * (4 * 1024 * 1024))

    with pytest.raises(DocumentValidationError) as error:
        validate_document_bytes(
            "compressed.docx",
            payload,
            max_size_bytes=5 * 1024 * 1024,
            max_uncompressed_bytes=5 * 1024 * 1024,
            max_single_entry_bytes=5 * 1024 * 1024,
        )

    assert error.value.code == "suspicious_compression"


def test_parser_worker_environment_omits_application_secrets(monkeypatch) -> None:
    secret_keys = {
        "DATABASE_URL": "postgresql://user:secret@example.invalid/db",
        "LLM_API_KEY": "fake-llm-secret",
        "JWT_SECRET": "fake-jwt-secret",
        "THESISCHECK_TEST_SECRET": "must-not-cross-worker-boundary",
    }
    for key, value in secret_keys.items():
        monkeypatch.setenv(key, value)

    child_environment = worker_client._worker_environment()

    assert child_environment
    assert set(child_environment).issubset(
        {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL"}
    )
    assert not (set(secret_keys) & set(child_environment))
    assert all(value not in child_environment.values() for value in secret_keys.values())


async def _run_body_guard_with_headers(
    headers: list[tuple[bytes, bytes]],
) -> tuple[int, dict[str, object], bool, dict[str, str]]:
    called = False
    sent: list[dict[str, object]] = []
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/inspect",
        "raw_path": b"/api/v1/inspect",
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 1234),
        "server": ("test", 80),
    }

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    async def downstream(app_scope, app_receive, app_send) -> None:
        nonlocal called
        called = True
        response = JSONResponse({"ok": True})
        await response(app_scope, app_receive, app_send)

    middleware = RequestBodyLimitMiddleware(downstream, max_body_bytes=16)
    await middleware(scope, receive, send)
    start = next(message for message in sent if message["type"] == "http.response.start")
    body_message = next(
        message for message in sent if message["type"] == "http.response.body"
    )
    body = json.loads(body_message["body"].decode("utf-8"))
    response_headers = {
        key.decode("latin-1").lower(): value.decode("latin-1")
        for key, value in start["headers"]
    }
    return int(start["status"]), body, called, response_headers


@pytest.mark.parametrize(
    "headers",
    [
        [(b"content-length", b"not-a-number")],
        [(b"content-length", b"-1")],
        [(b"content-length", b"12"), (b"content-length", b"13")],
    ],
)
def test_invalid_or_conflicting_content_length_is_rejected_before_app(
    headers: list[tuple[bytes, bytes]],
) -> None:
    status, body, called, response_headers = asyncio.run(
        _run_body_guard_with_headers(headers)
    )

    assert status == 400
    assert body["detail"]["code"] == "invalid_content_length"
    assert called is False
    assert response_headers["cache-control"] == "no-store"
    assert response_headers["x-content-type-options"] == "nosniff"
    assert response_headers["x-frame-options"] == "DENY"
