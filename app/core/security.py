"""Lightweight API request guards for local/demo deployments.

The in-memory limiter is per process. Production deployments still need a
shared limiter at the trusted reverse proxy or another shared store.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from math import ceil
from typing import Any
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class InspectionGuardMiddleware(BaseHTTPMiddleware):
    """Rate-limit document-processing POSTs and set baseline response headers."""

    protected_paths = frozenset({"/api/v1/inspect", "/api/v1/report"})

    def __init__(
        self,
        app,
        *,
        max_requests: int = 20,
        window_seconds: int = 60,
        max_tracked_clients: int = 10_000,
    ) -> None:
        super().__init__(app)
        if max_requests < 1 or window_seconds < 1 or max_tracked_clients < 1:
            raise ValueError("Rate-limit values must be positive")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.max_tracked_clients = max_tracked_clients
        self._requests: dict[str, deque[float]] = {}
        self._last_cleanup = 0.0
        self._lock = threading.Lock()

    async def dispatch(self, request: Request, call_next) -> Response:
        is_inspection_request = (
            request.method == "POST" and request.url.path in self.protected_paths
        )
        if is_inspection_request:
            client_host = request.client.host if request.client else "unknown"
            allowed, retry_after = self._allow_request(client_host)
            if not allowed:
                response = JSONResponse(
                    status_code=429,
                    content={
                        "detail": {
                            "code": "rate_limit_exceeded",
                            "message": (
                                "تعداد درخواست‌های بررسی فایل بیش از حد مجاز است؛ "
                                "کمی بعد دوباره تلاش کنید."
                            ),
                        }
                    },
                    headers={"Retry-After": str(retry_after)},
                )
                return self._secure_headers(response, no_store=True)

        response = await call_next(request)
        return self._secure_headers(response, no_store=is_inspection_request)

    def _allow_request(self, client_host: str) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            if now - self._last_cleanup >= self.window_seconds:
                stale = [
                    key
                    for key, timestamps in self._requests.items()
                    if not timestamps or timestamps[-1] <= cutoff
                ]
                for key in stale:
                    self._requests.pop(key, None)
                self._last_cleanup = now

            timestamps = self._requests.get(client_host)
            if timestamps is None:
                if len(self._requests) >= self.max_tracked_clients:
                    return False, self.window_seconds
                timestamps = deque()
                self._requests[client_host] = timestamps

            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()

            if len(timestamps) >= self.max_requests:
                retry_after = max(1, ceil(self.window_seconds - (now - timestamps[0])))
                return False, retry_after

            timestamps.append(now)
            return True, 0

    @staticmethod
    def _secure_headers(response: Response, *, no_store: bool) -> Response:
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if no_store:
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
        return response



class RequestBodyLimitMiddleware:
    """Cap raw request bytes before multipart parsing on document upload routes.

    The middleware streams ASGI receive messages and does not buffer the entire
    request itself. These file-upload routes consume the body before their
    handlers run, allowing an oversized streamed body to be converted to HTTP 413.
    """

    protected_paths = frozenset({"/api/v1/inspect", "/api/v1/report"})

    def __init__(self, app: ASGIApp, *, max_body_bytes: int) -> None:
        if max_body_bytes < 1:
            raise ValueError("max_body_bytes must be positive")
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path", "")).rstrip("/") or "/"
        if scope.get("method") != "POST" or path not in self.protected_paths:
            await self.app(scope, receive, send)
            return

        lengths = [
            value
            for name, value in scope.get("headers", [])
            if name.lower() == b"content-length"
        ]
        if lengths:
            try:
                parsed_lengths = {int(value.decode("ascii").strip()) for value in lengths}
            except (UnicodeDecodeError, ValueError):
                await self._send_error(
                    scope, receive, send,
                    status_code=400,
                    code="invalid_content_length",
                    message="هدر اندازهٔ درخواست معتبر نیست.",
                )
                return
            if len(parsed_lengths) != 1 or next(iter(parsed_lengths)) < 0:
                await self._send_error(
                    scope, receive, send,
                    status_code=400,
                    code="invalid_content_length",
                    message="هدر اندازهٔ درخواست معتبر نیست.",
                )
                return
            if next(iter(parsed_lengths)) > self.max_body_bytes:
                await self._send_error(
                    scope, receive, send,
                    status_code=413,
                    code="request_body_too_large",
                    message="حجم کل درخواست بیش از حد مجاز است.",
                )
                return

        received_bytes = 0
        body_too_large = False
        response_started = False

        async def bounded_receive() -> dict[str, Any]:
            nonlocal received_bytes, body_too_large
            if body_too_large:
                return {"type": "http.request", "body": b"", "more_body": False}
            message = await receive()
            if message.get("type") == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > self.max_body_bytes:
                    body_too_large = True
                    return {"type": "http.request", "body": b"", "more_body": False}
            return message

        async def guarded_send(message: dict[str, Any]) -> None:
            nonlocal response_started
            if body_too_large:
                return
            if message.get("type") == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, bounded_receive, guarded_send)
        except Exception:
            if not body_too_large:
                raise

        if body_too_large and not response_started:
            await self._send_error(
                scope, receive, send,
                status_code=413,
                code="request_body_too_large",
                message="حجم کل درخواست بیش از حد مجاز است.",
            )

    @staticmethod
    async def _send_error(
        scope: Scope,
        receive: Receive,
        send: Send,
        *,
        status_code: int,
        code: str,
        message: str,
    ) -> None:
        response = JSONResponse(
            status_code=status_code,
            content={"detail": {"code": code, "message": message}},
        )
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        await response(scope, receive, send)
