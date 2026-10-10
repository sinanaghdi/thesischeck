"""Best-effort text extraction from machine-readable PDF files using pdfplumber."""

from __future__ import annotations

import io
import re

import pdfplumber

from app.parsing.normalization import normalize_for_comparison
from app.schemas.document import DocumentElement, NormalizedDocument, ParseDiagnostic

_HEADING_RE = re.compile(
    r"^\s*(?:فصل\s+[\d۰-۹٠-٩]+|chapter\s+\d+|چکیده|abstract|منابع|مراجع|references|"
    r"فهرست\s+مطالب|contents|\d+(?:\.\d+){0,3}\s+\S{2,})\s*$",
    re.IGNORECASE,
)


def parse_pdf(content: bytes, filename: str) -> NormalizedDocument:
    """Extract text and page locations; formatting/style checks remain unavailable."""
    elements: list[DocumentElement] = []
    diagnostics: list[ParseDiagnostic] = []
    headings: list[str] = []
    pages_with_text = 0
    paragraph_count = 0
    line_count = 0

    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            page_count = len(pdf.pages)
            if page_count == 0:
                raise ValueError("PDF هیچ صفحه قابل خواندنی ندارد.")
            for page_number, page in enumerate(pdf.pages, start=1):
                text = page.extract_text(layout=False) or ""
                if text.strip():
                    pages_with_text += 1
                if "\n\n" in text:
                    blocks = [
                        block.strip()
                        for block in re.split(r"\n\s*\n", text)
                        if block.strip()
                    ]
                else:
                    # Avoid classifying a whole page as one heading when the extractor
                    # returns line breaks but no blank-line paragraph separators.
                    blocks = [line.strip() for line in text.splitlines() if line.strip()]
                for block in blocks:
                    for line in block.splitlines():
                        if not line.strip():
                            continue
                        line_count += 1
                        if _HEADING_RE.match(line.strip()):
                            headings.append(line.strip())
                    is_heading = _HEADING_RE.match(block.strip()) is not None
                    paragraph_count += 0 if is_heading else 1
                    elements.append(
                        DocumentElement(
                            element_id=f"pdf-p{page_number:04d}-e{len(elements) + 1:05d}",
                            kind="heading" if is_heading else "paragraph",
                            text=block[:10_000],
                            normalized_text=normalize_for_comparison(block)[:10_000],
                            heading_level=1 if is_heading else None,
                            heading_path=[headings[-1]] if headings else [],
                            page_number=page_number,
                            source_index=len(elements),
                            metadata={"extraction": "pdfplumber", "text_length": len(block)},
                        )
                    )
    except Exception as exc:  # Library-specific parse errors vary by malformed PDF.
        raise ValueError("PDF قابل استخراج نیست یا ساختار آن خراب است.") from exc

    if pages_with_text == 0:
        diagnostics.append(
            ParseDiagnostic(
                code="pdf_no_text_layer",
                message=(
                    "متن قابل استخراج در PDF پیدا نشد؛ احتمالاً فایل اسکن‌شده است. "
                    "OCR در این نسخه فعال نیست."
                ),
                severity="warning",
            )
        )
    diagnostics.extend(
        [
            ParseDiagnostic(
                code="pdf_style_checks_unavailable",
                message=(
                    "اطلاعاتی مانند قلم منبع، سبک Word، حاشیه‌های سند اصلی و ترتیب "
                    "واقعی بخش‌ها از PDF به‌طور کامل قابل بررسی نیست."
                ),
                severity="warning",
            ),
            ParseDiagnostic(
                code="pdf_layout_best_effort",
                message=(
                    "استخراج پاراگراف و عنوان از PDF تقریبی است؛ ستون‌ها، فرمول‌ها و "
                    "متن دوسویه ممکن است به بازبینی دستی نیاز داشته باشند."
                ),
                severity="info",
            ),
        ]
    )
    return NormalizedDocument(
        source_format="pdf",
        file_name=filename,
        elements=elements,
        diagnostics=diagnostics,
        page_count=page_count,
        parsing_complete=True,
        format_metadata={
            "pages_with_text": pages_with_text,
            "line_count": line_count,
            "paragraph_count": paragraph_count,
            "heading_count": len(headings),
            "ocr_available": False,
            "style_metadata_available": False,
        },
    )
