"""Upload inspection endpoint; input is parsed in memory and never persistently stored."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.parsing.dispatcher import parse_document
from app.parsing.safety import DocumentValidationError
from app.rules.engine import run_rules
from app.rules.findings import CheckReport
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
    checks: CheckReport
    privacy_note: str


def summarize_document(
    document: NormalizedDocument, checks: CheckReport
) -> InspectionSummary:
    """Return a bounded parser summary and deterministic findings."""
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
        checks=checks,
        privacy_note=(
            "فایل در این نسخه برای همین درخواست و در حافظه موقت پردازش می‌شود؛ "
            "این API فایل یا گزارش را در فضای ذخیره‌سازی دائمی نگه نمی‌دارد و از سرویس "
            "بیرونی هوش مصنوعی استفاده نمی‌کند."
        ),
    )


@router.post("/inspect", response_model=InspectionSummary)
async def inspect_document(file: UploadFile = File(...)) -> InspectionSummary:
    """Validate, parse and run configured deterministic checks; never saves the upload."""
    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    filename = file.filename or "document"
    try:
        content = await file.read(max_bytes + 1)
        if len(content) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"حجم فایل نباید بیشتر از {settings.max_upload_mb} مگابایت باشد.",
            )
        document = await run_in_threadpool(
            parse_document,
            filename,
            content,
            max_size_bytes=max_bytes,
        )
        ruleset = load_ruleset(RULESET_PATH)
        checks = await run_in_threadpool(run_rules, document, ruleset)
        return summarize_document(document, checks)
    except DocumentValidationError as exc:
        status_code = 413 if exc.code == "file_too_large" else 400
        raise HTTPException(
            status_code=status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        # Do not return internal exception details or source text to the browser.
        raise HTTPException(
            status_code=500,
            detail="پردازش فایل یا اجرای قواعد قابل انجام نبود؛ گزارش خطا نباید شامل متن سند باشد.",
        ) from exc
    finally:
        await file.close()
