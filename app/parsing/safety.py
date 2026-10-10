"""In-memory upload validation. Never extract archive members to the filesystem."""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import PurePath


@dataclass(slots=True)
class DocumentValidationError(ValueError):
    """A safe, user-displayable validation failure."""

    code: str
    message: str

    def __str__(self) -> str:
        return self.message


class DocumentParseError(ValueError):
    """A parser failure with a deliberately sanitized user-facing message."""


_ALLOWED_EXTENSIONS = {".docx", ".pdf"}
_PDF_HEADER = re.compile(rb"%PDF-\d\.\d")
_REQUIRED_DOCX_ENTRIES = {"[Content_Types].xml", "word/document.xml"}


def safe_display_filename(filename: str | None) -> str:
    """Return a display-only basename without control characters or path components."""
    raw = (filename or "document").replace("\\", "/").split("/")[-1]
    raw = "".join(char for char in raw if char.isprintable() and char not in "\x00\r\n")
    raw = raw.strip().strip(".")
    return raw[:180] or "document"


def validate_document_bytes(
    filename: str | None,
    content: bytes,
    *,
    max_size_bytes: int,
    max_zip_entries: int = 10_000,
    max_uncompressed_bytes: int = 250 * 1024 * 1024,
    max_single_entry_bytes: int = 64 * 1024 * 1024,
) -> str:
    """Validate extension, signature, and DOCX ZIP limits; return the detected format."""
    safe_name = safe_display_filename(filename)
    suffix = PurePath(safe_name).suffix.lower()
    if suffix == ".docm":
        raise DocumentValidationError(
            "macro_file_rejected", "فایل‌های دارای ماکرو (.docm) پذیرفته نمی‌شوند."
        )
    if suffix not in _ALLOWED_EXTENSIONS:
        raise DocumentValidationError(
            "unsupported_extension",
            "فقط فایل‌های Word با پسوند .docx و فایل‌های .pdf پذیرفته می‌شوند.",
        )
    if not content:
        raise DocumentValidationError("empty_file", "فایل خالی است.")
    if len(content) > max_size_bytes:
        max_mb = max_size_bytes // (1024 * 1024)
        raise DocumentValidationError(
            "file_too_large", f"حجم فایل نباید بیشتر از {max_mb} مگابایت باشد."
        )

    if suffix == ".pdf":
        # The PDF specification permits a small preamble before the header.
        if not _PDF_HEADER.search(content[:1024]):
            raise DocumentValidationError(
                "signature_mismatch", "محتوای فایل با ساختار PDF سازگار نیست."
            )
        return "pdf"

    if not zipfile.is_zipfile(io.BytesIO(content)):
        raise DocumentValidationError(
            "invalid_docx", "فایل DOCX معتبر یا قابل خواندن نیست."
        )
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) > max_zip_entries:
                raise DocumentValidationError(
                    "archive_entry_limit", "تعداد اجزای داخلی فایل بیش از حد مجاز است."
                )
            names = {entry.filename for entry in entries}
            if not _REQUIRED_DOCX_ENTRIES.issubset(names):
                raise DocumentValidationError(
                    "invalid_docx", "ساختار داخلی فایل با سند Word سازگار نیست."
                )
            if any(name.lower().endswith("vbaproject.bin") for name in names):
                raise DocumentValidationError(
                    "macro_content_rejected", "فایل شامل محتوای ماکرو است و پذیرفته نمی‌شود."
                )

            total_uncompressed = 0
            for entry in entries:
                if entry.flag_bits & 0x1:
                    raise DocumentValidationError(
                        "encrypted_archive", "فایل‌های Word رمزگذاری‌شده پذیرفته نمی‌شوند."
                    )
                if entry.file_size > max_single_entry_bytes:
                    raise DocumentValidationError(
                        "archive_entry_too_large", "یکی از اجزای داخلی فایل بیش از حد بزرگ است."
                    )
                total_uncompressed += entry.file_size
                if total_uncompressed > max_uncompressed_bytes:
                    raise DocumentValidationError(
                        "archive_too_large", "حجم بازشده فایل بیش از حد مجاز است."
                    )
                if entry.file_size > 1024 * 1024 and entry.compress_size == 0:
                    raise DocumentValidationError(
                        "suspicious_compression", "ساختار فشرده‌سازی فایل مشکوک است."
                    )
                if entry.compress_size and entry.file_size / entry.compress_size > 1000:
                    raise DocumentValidationError(
                        "suspicious_compression", "نسبت فشرده‌سازی فایل بیش از حد مجاز است."
                    )
            content_types = archive.read("[Content_Types].xml").lower()
            if b"macroenabled" in content_types:
                raise DocumentValidationError(
                    "macro_content_rejected",
                    "فایل دارای نوع محتوای ماکرو است و پذیرفته نمی‌شود.",
                )
    except DocumentValidationError:
        raise
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError) as exc:
        raise DocumentValidationError(
            "invalid_docx", "فایل DOCX خراب یا غیرقابل خواندن است."
        ) from exc

    return "docx"
