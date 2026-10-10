from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.reports import render_pdf
from app.reports.render_pdf import PdfExportUnavailable

client = TestClient(app)
ROOT = Path(__file__).resolve().parents[2]


def upload_synthetic_docx():
    content = (ROOT / "tests" / "fixtures" / "synthetic_bad.docx").read_bytes()
    return {
        "file": (
            "synthetic_bad.docx",
            content,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }


def test_export_json_is_machine_readable_and_explainable():
    response = client.post("/api/v1/report?format=json", files=upload_synthetic_docx())
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert 'attachment; filename="thesischeck-report.json"' in response.headers["content-disposition"]
    report = response.json()
    assert report["schema_version"] == "1.0"
    assert report["score_formula_en"]
    assert 0 < report["coverage_percent"] < 100
    assert report["ruleset_verified"] is False
    assert "checks" in report


def test_export_html_is_self_contained_and_right_to_left():
    response = client.post("/api/v1/report?format=html", files=upload_synthetic_docx())
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert 'lang="fa" dir="rtl"' in response.text
    assert "روش محاسبه امتیاز" in response.text
    assert "محدودیت‌های تحلیل" in response.text
    assert "https://" not in response.text


def test_export_pdf_uses_html_to_pdf_renderer(monkeypatch):
    monkeypatch.setattr(render_pdf, "render_pdf_bytes", lambda html: b"%PDF-1.4 synthetic")
    response = client.post("/api/v1/report?format=pdf", files=upload_synthetic_docx())
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-1.4")


def test_pdf_export_fails_with_actionable_message_when_browser_unavailable(monkeypatch):
    def unavailable(_html):
        raise PdfExportUnavailable("browser not available")

    monkeypatch.setattr(render_pdf, "render_pdf_bytes", unavailable)
    response = client.post("/api/v1/report?format=pdf", files=upload_synthetic_docx())
    assert response.status_code == 503
    assert "Chromium" in response.json()["detail"]
