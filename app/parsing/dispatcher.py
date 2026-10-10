"""Safe dispatch between the supported document parsers."""

from __future__ import annotations

from app.parsing.docx_parser import parse_docx
from app.parsing.pdf_parser import parse_pdf
from app.parsing.safety import safe_display_filename, validate_document_bytes
from app.schemas.document import NormalizedDocument


def parse_document(
    filename: str | None,
    content: bytes,
    *,
    max_size_bytes: int,
) -> NormalizedDocument:
    """Validate and parse supported input in memory without persistent storage."""
    display_name = safe_display_filename(filename)
    file_format = validate_document_bytes(filename, content, max_size_bytes=max_size_bytes)
    try:
        if file_format == "docx":
            return parse_docx(content, display_name)
        if file_format == "pdf":
            return parse_pdf(content, display_name)
    except Exception as exc:
        # Do not expose parser internals; malformed documents should fail as a clear 422.
        if file_format == "docx":
            message = "ساختار داخلی DOCX خراب است یا بخشی از آن قابل استخراج نیست."
        else:
            message = "ساختار PDF خراب است یا بخشی از آن قابل استخراج نیست."
        raise ValueError(message) from exc
    # Keeps dispatch fail-closed if another format is added without a parser.
    raise ValueError("قالب فایل پشتیبانی نمی‌شود.")
