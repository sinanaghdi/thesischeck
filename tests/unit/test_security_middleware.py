import asyncio
import json

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from app.core.security import InspectionGuardMiddleware, RequestBodyLimitMiddleware


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



def make_body_limited_app(max_body_bytes: int = 16) -> tuple[FastAPI, dict[str, bool]]:
    app = FastAPI()
    app.add_middleware(RequestBodyLimitMiddleware, max_body_bytes=max_body_bytes)
    observed = {"called": False}

    @app.post("/api/v1/inspect")
    async def inspect(request: Request) -> dict[str, int]:
        observed["called"] = True
        return {"size": len(await request.body())}

    return app, observed


def test_content_length_over_limit_is_rejected_before_route_handler() -> None:
    app, observed = make_body_limited_app()
    response = TestClient(app).post("/api/v1/inspect", content=b"x" * 17)

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "request_body_too_large"
    assert observed["called"] is False
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_body_at_limit_is_accepted() -> None:
    app, observed = make_body_limited_app()
    response = TestClient(app).post("/api/v1/inspect", content=b"x" * 16)

    assert response.status_code == 200
    assert response.json()["size"] == 16
    assert observed["called"] is True


def test_streamed_body_without_content_length_is_rejected() -> None:
    async def run_case() -> tuple[int, dict[str, object]]:
        messages = [
            {"type": "http.request", "body": b"a" * 10, "more_body": True},
            {"type": "http.request", "body": b"b" * 10, "more_body": False},
        ]
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
            "headers": [],
            "client": ("127.0.0.1", 1234),
            "server": ("test", 80),
        }

        async def receive() -> dict[str, object]:
            if messages:
                return messages.pop(0)
            return {"type": "http.disconnect"}

        async def send(message: dict[str, object]) -> None:
            sent.append(message)

        async def upload_app(scope, receive, send) -> None:
            while True:
                message = await receive()
                if message.get("type") == "http.disconnect":
                    return
                if message.get("type") == "http.request" and not message.get("more_body", False):
                    break
            response = JSONResponse({"ok": True})
            await response(scope, receive, send)

        middleware = RequestBodyLimitMiddleware(upload_app, max_body_bytes=16)
        await middleware(scope, receive, send)
        start = next(message for message in sent if message["type"] == "http.response.start")
        body = next(message for message in sent if message["type"] == "http.response.body")
        return int(start["status"]), json.loads(body["body"].decode("utf-8"))

    status, body = asyncio.run(run_case())
    assert status == 413
    assert body["detail"]["code"] == "request_body_too_large"
