from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.parsing.safety import DocumentValidationError
from app.parsing import worker_client


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "synthetic_bad.docx"


def parse_args() -> dict[str, int]:
    return {
        "max_size_bytes": 30 * 1024 * 1024,
        "timeout_seconds": 35,
        "cpu_seconds": 25,
        "memory_mb": 1024,
        "concurrency": 1,
    }


def test_parser_subprocess_round_trips_a_docx_fixture() -> None:
    document = worker_client.parse_document_in_worker(
        "synthetic_bad.docx",
        FIXTURE.read_bytes(),
        **parse_args(),
    )

    assert document.source_format == "docx"
    assert document.elements
    assert document.file_name == "synthetic_bad.docx"


def test_parser_subprocess_returns_controlled_validation_errors() -> None:
    with pytest.raises(DocumentValidationError) as error:
        worker_client.parse_document_in_worker(
            "unsupported.txt",
            b"not a supported document",
            **parse_args(),
        )

    assert error.value.code == "unsupported_extension"


def test_parser_timeout_is_translated_to_a_safe_worker_error(monkeypatch) -> None:
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], timeout=1)

    monkeypatch.setattr(worker_client.subprocess, "run", timeout)

    with pytest.raises(worker_client.ParserWorkerTimeout):
        worker_client.parse_document_in_worker(
            "synthetic_bad.docx",
            FIXTURE.read_bytes(),
            **parse_args(),
        )
