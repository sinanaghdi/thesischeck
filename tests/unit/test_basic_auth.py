"""Regression tests for the optional shared Basic Auth demo gate."""

from __future__ import annotations

import base64

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.core.security import BasicAuthMiddleware

USERNAME = "thesischeck-user"
PASSWORD = "a-long-test-password-that-is-never-used-in-production"


def build_test_client(
    *, enabled: bool = True, username: str = USERNAME, password: str = PASSWORD
) -> TestClient:
    app = FastAPI()

    @app.get("/private")
    def private() -> dict[str, str]:
        return {"content": "protected"}

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    gated = BasicAuthMiddleware(
        app,
        enabled=enabled,
        username=username if enabled else None,
        password=password if enabled else None,
    )
    return TestClient(gated)


def encoded_credentials(username: str, password: str) -> str:
    raw = f"{username}:{password}".encode("utf-8")
    return f"Basic {base64.b64encode(raw).decode('ascii')}"


def test_private_route_requires_auth_and_uses_no_store_challenge() -> None:
    response = build_test_client().get("/private")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == 'Basic realm="ThesisCheck", charset="UTF-8"'
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.json()["detail"]["code"] == "authentication_required"


def test_correct_basic_credentials_allow_access() -> None:
    response = build_test_client().get(
        "/private",
        headers={"Authorization": encoded_credentials(USERNAME, PASSWORD)},
    )

    assert response.status_code == 200
    assert response.json() == {"content": "protected"}
    assert response.headers["x-frame-options"] == "DENY"


def test_utf8_credentials_are_compared_as_bytes() -> None:
    username = "کاربر-آزمایشی"
    password = "گذرواژه-آزمایشی-بسیار-بلند-برای-تست"
    client = build_test_client(username=username, password=password)

    response = client.get(
        "/private",
        headers={"Authorization": encoded_credentials(username, password)},
    )

    assert response.status_code == 200


@pytest.mark.parametrize(
    "authorization",
    [
        "Bearer not-a-basic-token",
        "Basic not-base64",
        "Basic " + base64.b64encode(b"missing-colon").decode("ascii"),
        "Basic " + base64.b64encode(b"only-user:wrong-password").decode("ascii"),
        "Basic " + ("A" * 8193),
    ],
)
def test_malformed_or_invalid_credentials_are_rejected(authorization: str) -> None:
    response = build_test_client().get("/private", headers={"Authorization": authorization})

    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers


def test_public_health_route_is_exempt_but_other_routes_are_gated() -> None:
    client = build_test_client()

    assert client.get("/health").status_code == 200
    assert client.get("/private").status_code == 401


def test_disabled_basic_auth_preserves_local_development_flow() -> None:
    client = build_test_client(enabled=False)

    assert client.get("/private").status_code == 200


def test_enabled_settings_reject_missing_or_short_passwords() -> None:
    with pytest.raises(ValidationError):
        Settings(
            basic_auth_enabled=True,
            basic_auth_username="demo",
            basic_auth_password="short",
        )

    valid = Settings(
        basic_auth_enabled=True,
        basic_auth_username="demo",
        basic_auth_password=PASSWORD,
    )
    assert valid.basic_auth_enabled is True
