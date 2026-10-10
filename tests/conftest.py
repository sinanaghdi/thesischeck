"""Shared test setup, including reproducible synthetic document fixtures."""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def ensure_synthetic_documents() -> None:
    """Generate test DOCX files on fresh clones; never commit generated binaries."""
    root = Path(__file__).resolve().parents[1]
    subprocess.run(
        [sys.executable, str(root / "scripts" / "generate_fixtures.py")],
        cwd=root,
        check=True,
    )
