"""Lightweight API request guards for local/demo deployments.

The in-memory limiter is per process. Production deployments still need a
shared limiter at the trusted reverse proxy or another shared store.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from math import ceil

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
