"""Lightweight API request guards for local/demo deployments.

The in-memory limiter is per process. Production deployments still need a
shared limiter at the trusted reverse proxy or another shared store.
"""
from __future__ import annotations

import base64
import binascii
import hmac
import threading
import time
from collections import deque
from math import ceil
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send


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


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """Optional shared-password gate for demos; not a per-user account system."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        enabled: bool = False,
        username: str | None = None,
        password: str | None = None,
        exempt_paths: frozenset[str] | set[str] = frozenset({"/health"}),
        realm: str = "ThesisCheck",
        max_header_bytes: int = 8192,
    ) -> None:
        super().__init__(app)
        if max_header_bytes < 128:
            raise ValueError("max_header_bytes must be at least 128")
        if enabled and (
            not username
            or len(username.strip()) < 3
            or username != username.strip()
            or not password
            or len(password) < 24
        ):
            raise ValueError(
                "Enabled Basic Auth requires a clean username and a password of at least 24 characters"
            )
        self.enabled = enabled
        self.username = username or ""
        self.password = password or ""
        self.exempt_paths = frozenset(exempt_paths)
        self.realm = realm.replace('"', "")
        self.max_header_bytes = max_header_bytes

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self.enabled or request.url.path in self.exempt_paths:
            return await call_next(request)

        if not self._is_authorized(request.headers.get("authorization", "")):
            return JSONResponse(
                status_code=401,
                content={
                    "detail": {
                        "code": "authentication_required",
                        "message": "برای دسترسی به این بخش، نام کاربری و گذرواژهٔ معتبر وارد کنید.",
                    }
                },
                headers={
                    "WWW-Authenticate": f'Basic realm="{self.realm}", charset="UTF-8"',
                    "Cache-Control": "no-store",
                    "Pragma": "no-cache",
                    "X-Content-Type-Options": "nosniff",
                    "Referrer-Policy": "no-referrer",
                    "X-Frame-Options": "DENY",
                },
            )

        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    def _is_authorized(self, authorization: str) -> bool:
        if not authorization or len(authorization) > self.max_header_bytes:
            return False
        scheme, separator, encoded = authorization.partition(" ")
        if not separator or scheme.lower() != "basic" or not encoded:
            return False
        try:
            decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            return False

        supplied_username, separator, supplied_password = decoded.partition(":")
        if not separator:
            return False
        username_matches = hmac.compare_digest(
            supplied_username.encode("utf-8"), self.username.encode("utf-8")
        )
        password_matches = hmac.compare_digest(
            supplied_password.encode("utf-8"), self.password.encode("utf-8")
        )
        return username_matches and password_matches


class RequestBodyLimitMiddleware:
    """Cap raw request bytes before multipart parsing on document upload routes.

    The middleware streams ASGI receive messages and does not buffer the entire
    request itself. These file-upload routes consume the body before their
    handlers run, allowing an oversized streamed body to be converted to HTTP 413.
    """

    protected_paths = frozenset({"/api/v1/inspect", "/api/v1/report"})

    def __init__(
        self,
        app: ASGIApp,
        *,
        max_body_bytes: int,
        protected_paths: frozenset[str] | set[str] | None = None,
    ) -> None:
        if max_body_bytes < 1:
            raise ValueError("max_body_bytes must be positive")
        self.app = app
        self.max_body_bytes = max_body_bytes
        self.protected_paths = (
            frozenset(protected_paths) if protected_paths is not None else type(self).protected_paths
        )

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
