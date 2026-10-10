"""Supervise parser subprocesses and validate their machine-readable result."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.parsing.safety import (
    DocumentParseError,
    DocumentValidationError,
    safe_display_filename,
)
from app.schemas.document import NormalizedDocument

_MAX_WORKER_RESPONSE_BYTES = 64 * 1024 * 1024


class ParserWorkerError(RuntimeError):
    """Base class for safe, user-displayable worker failures."""


class ParserWorkerTimeout(ParserWorkerError):
    """The parser exceeded its wall-clock deadline."""


class ParserWorkerBusy(ParserWorkerError):
    """No parser worker slot became available quickly enough."""


class ParserWorkerFailure(ParserWorkerError):
    """The subprocess failed or returned an invalid response."""


@lru_cache(maxsize=8)
def _worker_slots(concurrency: int) -> threading.BoundedSemaphore:
    return threading.BoundedSemaphore(value=concurrency)


def _worker_environment() -> dict[str, str]:
    """Pass only runtime essentials; do not forward application secrets."""
    allowed = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL")
    return {key: os.environ[key] for key in allowed if os.environ.get(key)}


def parse_document_in_worker(
    filename: str | None,
    content: bytes,
    *,
    max_size_bytes: int,
    timeout_seconds: int,
    cpu_seconds: int,
    memory_mb: int,
    concurrency: int = 2,
    slot_wait_seconds: float = 1.0,
) -> NormalizedDocument:
    """Parse one input in a supervised child process and return a validated model.

    The child receives bytes over stdin and writes JSON to stdout. It inherits
    neither application secrets nor arbitrary environment variables. The
    semaphore is per process; deployments with multiple replicas need an
    external concurrency/rate-control layer.
    """
    slots = _worker_slots(concurrency)
    if not slots.acquire(timeout=slot_wait_seconds):
        raise ParserWorkerBusy("No parser worker slot is available.")

    try:
        safe_filename = safe_display_filename(filename)
        command = [
            sys.executable,
            "-I",
            "-m",
            "app.parsing.worker",
            f"--filename={safe_filename}",
            f"--max-size-bytes={max_size_bytes}",
            f"--cpu-seconds={cpu_seconds}",
            f"--memory-mb={memory_mb}",
        ]
        try:
            completed = subprocess.run(
                command,
                input=content,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                cwd=Path(tempfile.gettempdir()),
                env=_worker_environment(),
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise ParserWorkerTimeout("Parser deadline exceeded.") from None
        except OSError:
            raise ParserWorkerFailure("Parser subprocess could not be started.") from None

        if completed.returncode != 0 or not completed.stdout:
            raise ParserWorkerFailure("Parser subprocess exited without a valid response.")
        if len(completed.stdout) > _MAX_WORKER_RESPONSE_BYTES:
            raise ParserWorkerFailure("Parser response exceeded the allowed size.")

        try:
            payload: dict[str, Any] = json.loads(completed.stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ParserWorkerFailure("Parser subprocess returned invalid JSON.") from None

        if payload.get("ok") is True:
            try:
                return NormalizedDocument.model_validate(payload["document"])
            except (KeyError, TypeError, ValueError):
                raise ParserWorkerFailure("Parser subprocess returned an invalid document.") from None

        kind = payload.get("kind")
        if kind == "validation":
            raise DocumentValidationError(
                str(payload.get("code", "invalid_document")),
                str(payload.get("message", "فایل قابل پردازش نیست.")),
            )
        if kind == "parse":
            raise DocumentParseError(str(payload.get("message", "ساختار فایل قابل استخراج نیست.")))
        raise ParserWorkerFailure("Parser subprocess failed while processing the document.")
    finally:
        slots.release()



def parse_document_via_service(
    filename: str | None,
    content: bytes,
    *,
    max_size_bytes: int,
    timeout_seconds: int,
    service_url: str | None,
    service_token: str | None,
) -> NormalizedDocument:
    """Send a document to a configured private parser service and validate its response."""
    import base64
    import socket
    import urllib.error
    import urllib.parse
    import urllib.request

    if not service_url or not service_token:
        raise ParserWorkerFailure("Parser service is not configured.")

    try:
        parsed_url = urllib.parse.urlsplit(service_url)
    except ValueError:
        raise ParserWorkerFailure("Parser service URL is invalid.") from None
    if (
        parsed_url.scheme not in {"http", "https"}
        or not parsed_url.hostname
        or parsed_url.username
        or parsed_url.password
        or parsed_url.path not in {"", "/"}
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise ParserWorkerFailure("Parser service URL is invalid.")

    if len(content) > max_size_bytes:
        max_mb = max_size_bytes // (1024 * 1024)
        raise DocumentValidationError(
            "file_too_large", f"حجم فایل نباید بیشتر از {max_mb} مگابایت باشد."
        )

    safe_filename = safe_display_filename(filename)
    encoded_filename = base64.urlsafe_b64encode(safe_filename.encode("utf-8")).decode("ascii")
    request = urllib.request.Request(
        f"{service_url.rstrip('/')}/internal/parse",
        data=content,
        headers={
            "Content-Type": "application/octet-stream",
            "X-Parser-Token": service_token,
            "X-Document-Filename-B64": encoded_filename,
        },
        method="POST",
    )

    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=timeout_seconds) as response:
            status_code = response.status
            raw_response = response.read(_MAX_WORKER_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        status_code = exc.code
        try:
            raw_response = exc.read(64 * 1024 + 1)
        finally:
            exc.close()
    except (TimeoutError, socket.timeout):
        raise ParserWorkerTimeout("Parser service deadline exceeded.") from None
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise ParserWorkerTimeout("Parser service deadline exceeded.") from None
        raise ParserWorkerFailure("Parser service could not be reached.") from None
    except OSError:
        raise ParserWorkerFailure("Parser service could not be reached.") from None

    if len(raw_response) > _MAX_WORKER_RESPONSE_BYTES:
        raise ParserWorkerFailure("Parser service response exceeded the allowed size.")

    try:
        payload: dict[str, Any] = json.loads(raw_response.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ParserWorkerFailure("Parser service returned invalid JSON.") from None

    if status_code == 200 and payload.get("ok") is True:
        try:
            return NormalizedDocument.model_validate(payload["document"])
        except (KeyError, TypeError, ValueError):
            raise ParserWorkerFailure("Parser service returned an invalid document.") from None

    error_detail = payload.get("detail")
    error_payload = error_detail if isinstance(error_detail, dict) else payload
    code = error_payload.get("code")
    message = error_payload.get("message")
    safe_message = (
        message if isinstance(message, str) and message else "ساختار فایل قابل پردازش نیست."
    )
    if status_code in {400, 413}:
        validation_code = code if isinstance(code, str) else "invalid_document"
        if status_code == 413 or validation_code == "request_body_too_large":
            validation_code = "file_too_large"
        raise DocumentValidationError(validation_code, safe_message)
    if status_code == 422:
        raise DocumentParseError(safe_message)
    if status_code == 503 and code == "parser_worker_busy":
        raise ParserWorkerBusy("No parser worker slot is available.")
    if status_code == 504 or code == "parser_timeout":
        raise ParserWorkerTimeout("Parser service deadline exceeded.")
    raise ParserWorkerFailure("Parser service failed to process the document.")
