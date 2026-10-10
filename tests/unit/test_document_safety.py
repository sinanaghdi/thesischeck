from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.parsing.safety import (
    DocumentValidationError,
    safe_display_filename,
    validate_document_bytes,
)


def make_minimal_docx() -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")
    return buffer.getvalue()


def test_rejects_macro_enabled_word_document() -> None:
    with pytest.raises(DocumentValidationError) as error:
        validate_document_bytes("thesis.docm", b"PK fake", max_size_bytes=1024)
    assert error.value.code == "macro_file_rejected"


def test_rejects_extension_signature_mismatch() -> None:
    with pytest.raises(DocumentValidationError) as error:
        validate_document_bytes("thesis.docx", b"plain text", max_size_bytes=1024)
    assert error.value.code == "invalid_docx"


def test_rejects_oversized_file_before_parsing() -> None:
    with pytest.raises(DocumentValidationError) as error:
        validate_document_bytes(
            "thesis.pdf", b"%PDF-1.4" + b"x" * 50, max_size_bytes=10
        )
    assert error.value.code == "file_too_large"


def test_validates_docx_package_signature_and_required_parts() -> None:
    assert (
        validate_document_bytes(
            "draft.docx", make_minimal_docx(), max_size_bytes=1024 * 1024
        )
        == "docx"
    )


def test_rejects_zip_without_required_docx_parts() -> None:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("other.txt", "not a Word document")
    with pytest.raises(DocumentValidationError) as error:
        validate_document_bytes("draft.docx", buffer.getvalue(), max_size_bytes=1024 * 1024)
    assert error.value.code == "invalid_docx"


def test_filename_is_display_only_basename() -> None:
    assert safe_display_filename(r"C:\Users\student\draft.docx") == "draft.docx"
    assert safe_display_filename("../../\n\x00") == "document"


def test_rejects_macro_payload_even_when_extension_is_docx() -> None:
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")
        archive.writestr("word/vbaProject.bin", b"synthetic macro marker")

    with pytest.raises(DocumentValidationError) as error:
        validate_document_bytes(
            "misnamed.docx", buffer.getvalue(), max_size_bytes=1024 * 1024
        )
    assert error.value.code == "macro_content_rejected"
