from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
ROOT = Path(__file__).resolve().parents[2]


def test_inspect_returns_summary_without_full_document_text() -> None:
    content = (ROOT / "tests" / "fixtures" / "synthetic_bad.docx").read_bytes()
    response = client.post(
        "/api/v1/inspect",
        files={
            "file": (
                "synthetic_bad.docx",
                content,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source_format"] == "docx"
    assert body["element_count"] > 0
    assert body["headings"]
    assert "عناصر شناسایی" not in response.text
    assert "privacy_note" in body


def test_inspect_rejects_unsupported_format() -> None:
    response = client.post("/api/v1/inspect", files={"file": ("thesis.docm", b"not accepted")})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "macro_file_rejected"


def test_inspect_page_contains_upload_form() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert 'id="inspect-form"' in response.text
    assert 'id="inspect-submit"' in response.text


def test_inspect_returns_controlled_error_for_malformed_docx_package() -> None:
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document")
    response = client.post(
        "/api/v1/inspect", files={"file": ("broken.docx", buffer.getvalue())}
    )
    assert response.status_code == 422
    assert "detail" in response.json()
