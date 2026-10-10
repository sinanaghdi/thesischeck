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
