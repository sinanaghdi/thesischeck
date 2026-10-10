"""Private-network parser service entry point for the Docker demo profile.

This app has no published port in Compose and is meant to be reachable only over
the private parser network. Parsing continues in a supervised subprocess.
"""
from __future__ import annotations

import base64
import binascii
import secrets
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.security import RequestBodyLimitMiddleware
from app.parsing.safety import (
    DocumentParseError,
    DocumentValidationError,
    safe_display_filename,
)
from app.parsing.worker_client import (
    ParserWorkerBusy,
    ParserWorkerFailure,
    ParserWorkerTimeout,
    parse_document_in_worker,
)

settings = get_settings()
app = FastAPI(
    title="ThesisCheck private parser",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.add_middleware(
    RequestBodyLimitMiddleware,
    max_body_bytes=settings.max_upload_mb * 1024 * 1024,
    protected_paths=frozenset({"/internal/parse"}),
)


def _response(payload: dict[str, Any], *, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=payload,
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok", "service": "thesischeck-parser"}


@app.post("/internal/parse")
async def parse_internal_document(request: Request) -> JSONResponse:
    """Accept one authenticated binary document from the web container."""
    settings = get_settings()
    expected_token = settings.parser_service_token or ""
    supplied_token = request.headers.get("x-parser-token", "")
    if len(expected_token) < 32 or not secrets.compare_digest(supplied_token, expected_token):
        return _response(
            {"ok": False, "code": "unauthorized", "message": "دسترسی مجاز نیست."},
            status_code=401,
        )

    media_type = request.headers.get("content-type", "").split(";", maxsplit=1)[0].strip().lower()
    if media_type != "application/octet-stream":
        return _response(
            {"ok": False, "code": "unsupported_media_type", "message": "نوع درخواست معتبر نیست."},
            status_code=415,
        )

    encoded_filename = request.headers.get("x-document-filename-b64", "")
    try:
        if not encoded_filename or len(encoded_filename) > 1024:
            raise ValueError("Invalid filename header")
        filename = base64.b64decode(
            encoded_filename.encode("ascii"),
            altchars=b"-_",
            validate=True,
        ).decode("utf-8")
        filename = safe_display_filename(filename)
    except (UnicodeEncodeError, UnicodeDecodeError, binascii.Error, ValueError):
        return _response(
            {"ok": False, "code": "invalid_filename", "message": "نام فایل معتبر نیست."},
            status_code=400,
        )

    content = await request.body()
    try:
        document = await run_in_threadpool(
            parse_document_in_worker,
            filename,
            content,
            max_size_bytes=settings.max_upload_mb * 1024 * 1024,
            timeout_seconds=settings.parser_worker_timeout_seconds,
            cpu_seconds=settings.parser_worker_cpu_seconds,
            memory_mb=settings.parser_worker_memory_mb,
            concurrency=settings.parser_worker_concurrency,
        )
    except DocumentValidationError as exc:
        status_code = 413 if exc.code == "file_too_large" else 400
        return _response(
            {"ok": False, "code": exc.code, "message": exc.message},
            status_code=status_code,
        )
    except DocumentParseError as exc:
        return _response(
            {"ok": False, "code": "document_parse_error", "message": str(exc)},
            status_code=422,
        )
    except ParserWorkerBusy:
        return _response(
            {"ok": False, "code": "parser_worker_busy", "message": "ظرفیت پردازش فایل تکمیل است؛ کمی بعد تلاش کنید."},
            status_code=503,
        )
    except ParserWorkerTimeout:
        return _response(
            {"ok": False, "code": "parser_timeout", "message": "مهلت پردازش فایل تمام شد."},
            status_code=504,
        )
    except ParserWorkerFailure:
        return _response(
            {"ok": False, "code": "parser_unavailable", "message": "پردازشگر فایل پاسخ معتبر نداد."},
            status_code=503,
        )
    except Exception:
        return _response(
            {"ok": False, "code": "parser_internal_error", "message": "پردازش فایل انجام نشد."},
            status_code=500,
        )

    return _response({"ok": True, "document": document.model_dump(mode="json")})
