from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_home_page_is_persian_and_discloses_phase_0_limit() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert 'lang="fa" dir="rtl"' in response.text
    assert "بارگذاری فایل و تحلیل پایان‌نامه فعال نیست" in response.text
