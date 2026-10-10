"""Document inspection and report-export endpoints; uploads are never persisted."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.parsing.dispatcher import parse_document
from app.parsing.safety import DocumentParseError, DocumentValidationError
from app.reports.render_html import render_html_report
from app.reports.scoring import HealthReport, build_health_report
from app.rules.engine import run_rules
from app.rules.loader import load_ruleset
from app.schemas.document import NormalizedDocument

router = APIRouter(prefix="/api/v1", tags=["document-inspection"])
PROJECT_ROOT = Path(__file__).resolve().parents[3]
RULESET_PATH = PROJECT_ROOT / "rulesets" / "mazandaran_engineering_example.yaml"


class InspectionSummary(BaseModel):
    file_name: str
    source_format: str
    parsing_complete: bool
    page_count: int | None = None
    element_count: int
    element_counts: dict[str, int]
    headings: list[dict[str, Any]] = Field(default_factory=list)
    preview_paragraphs: list[dict[str, str | int | None]] = Field(default_factory=list)
    format_metadata: dict[str, Any] = Field(default_factory=dict)
    diagnostics: list[dict[str, str]] = Field(default_factory=list)
    health_report: HealthReport
    privacy_note: str


def _process_document(
    filename: str,
    content: bytes,
    *,
    max_size_bytes: int,
) -> tuple[NormalizedDocument, HealthReport]:
    document = parse_document(filename, content, max_size_bytes=max_size_bytes)
    ruleset = load_ruleset(RULESET_PATH)
    checks = run_rules(document, ruleset)
    return document, build_health_report(document, checks, ruleset)


def summarize_document(
    document: NormalizedDocument, report: HealthReport
) -> InspectionSummary:
    """Return a bounded parser summary and the explainable report summary."""
    counts = Counter(element.kind for element in document.elements)
    headings = [
        {
            "element_id": element.element_id,
            "title": element.text[:240],
            "level": element.heading_level,
            "source_index": element.source_index,
        }
        for element in document.elements
        if element.kind == "heading"
    ][:50]
    previews = [
        {
            "element_id": element.element_id,
            "text": element.text[:240],
            "page_number": element.page_number,
        }
        for element in document.elements
        if element.kind in {"paragraph", "figure", "equation"} and element.text.strip()
    ][:5]
    diagnostics = [
        {"code": diagnostic.code, "message": diagnostic.message, "severity": diagnostic.severity}
        for diagnostic in document.diagnostics
    ]
    return InspectionSummary(
        file_name=document.file_name,
        source_format=document.source_format,
        parsing_complete=document.parsing_complete,
        page_count=document.page_count,
        element_count=len(document.elements),
        element_counts=dict(counts),
        headings=headings,
        preview_paragraphs=previews,
        format_metadata=document.format_metadata,
        diagnostics=diagnostics,
        health_report=report,
        privacy_note=(
            "فایل در این نسخه برای همین درخواست و در حافظه موقت پردازش می‌شود؛ "
            "این API فایل یا گزارش را در فضای ذخیره‌سازی دائمی نگه نمی‌دارد و از سرویس "
            "بیرونی هوش مصنوعی استفاده نمی‌کند."
        ),
    )


async def _read_and_process(file: UploadFile) -> tuple[NormalizedDocument, HealthReport]:
    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    try:
        content = await file.read(max_bytes + 1)
        if len(content) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"حجم فایل نباید بیشتر از {settings.max_upload_mb} مگابایت باشد.",
            )
        return await run_in_threadpool(
            _process_document,
            file.filename or "document",
            content,
            max_size_bytes=max_bytes,
        )
    except DocumentValidationError as exc:
        status_code = 413 if exc.code == "file_too_large" else 400
        raise HTTPException(
            status_code=status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except DocumentParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="پردازش فایل یا اجرای قواعد قابل انجام نبود؛ متن سند نباید در پیام خطا ثبت شود.",
        ) from None
    finally:
        await file.close()


@router.post("/inspect", response_model=InspectionSummary)
async def inspect_document(file: UploadFile = File(...)) -> InspectionSummary:
    """Validate, parse, score configured checks, and summarize one document."""
    document, report = await _read_and_process(file)
    return summarize_document(document, report)


@router.post("/report", tags=["report-export"])
async def export_report(
    file: UploadFile = File(...),
    output_format: Literal["json", "html", "pdf"] = Query(default="json", alias="format"),
) -> Response:
    """Return a downloadable report without saving the source document or report."""
    _document, report = await _read_and_process(file)
    if output_format == "json":
        content = json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        )
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="thesischeck-report.json"'},
        )

    html = render_html_report(report)
    if output_format == "html":
        return Response(
            content=html,
            media_type="text/html; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="thesischeck-report.html"'},
        )

    try:
        from app.reports.render_pdf import PdfExportUnavailable, render_pdf_bytes

        pdf_bytes = await run_in_threadpool(render_pdf_bytes, html)
    except PdfExportUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "خروجی PDF در این محیط آماده نیست. وابستگی اختیاری Playwright و مرورگر "
                "Chromium را طبق README نصب کنید."
            ),
        ) from exc
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="thesischeck-report.pdf"'},
    )
