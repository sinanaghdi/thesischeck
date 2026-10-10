"""FastAPI entry point for the Phase 0 scaffold."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import get_settings

BASE_DIR = Path(__file__).resolve().parent
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Persian-first thesis writing-quality and format-control assistant.",
    version="0.1.0",
    debug=settings.debug,
)
app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "web" / "static"),
    name="static",
)
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"request": request, "app_name": settings.app_name},
    )


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Liveness endpoint; database readiness will be added with persistence."""
    return {"status": "ok", "service": "thesischeck", "phase": "0"}
