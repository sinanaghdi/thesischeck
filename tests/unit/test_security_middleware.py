from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import InspectionGuardMiddleware


def make_limited_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        InspectionGuardMiddleware,
        max_requests=1,
        window_seconds=60,
    )

    @app.post("/api/v1/inspect")
    async def inspect() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/v1/report")
    async def report() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    return app


def test_second_inspection_request_is_rate_limited_with_retry_header() -> None:
    client = TestClient(make_limited_app())

    assert client.post("/api/v1/inspect").status_code == 200
    limited = client.post("/api/v1/inspect")

    assert limited.status_code == 429
    assert limited.json()["detail"]["code"] == "rate_limit_exceeded"
    assert int(limited.headers["retry-after"]) >= 1
    assert limited.headers["cache-control"] == "no-store"
    assert limited.headers["x-content-type-options"] == "nosniff"


def test_report_and_inspect_share_the_same_protection_bucket() -> None:
    client = TestClient(make_limited_app())

    assert client.post("/api/v1/inspect").status_code == 200
    limited = client.post("/api/v1/report")

    assert limited.status_code == 429


def test_non_inspection_routes_are_not_rate_limited_but_have_security_headers() -> None:
    client = TestClient(make_limited_app())

    assert client.get("/health").status_code == 200
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-frame-options"] == "DENY"
    assert "cache-control" not in response.headers or response.headers["cache-control"] != "no-store"
