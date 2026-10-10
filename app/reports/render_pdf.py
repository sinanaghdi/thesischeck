"""Optional HTML-to-PDF export using Playwright/Chromium for script shaping and RTL layout."""

from __future__ import annotations


class PdfExportUnavailable(RuntimeError):
    """Raised when the optional Playwright package or Chromium browser is unavailable."""


def render_pdf_bytes(html: str) -> bytes:
    """Render self-contained RTL HTML with Chromium. No remote resources are loaded."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise PdfExportUnavailable(
            "PDF export requires the optional 'pdf' extra and its Chromium browser."
        ) from exc

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(
                    locale="fa-IR",
                    reduced_motion="reduce",
                    viewport={"width": 1280, "height": 1600},
                )
                page.set_content(html, wait_until="networkidle")
                page.emulate_media(media="print")
                data = page.pdf(
                    format="A4",
                    print_background=True,
                    prefer_css_page_size=True,
                    margin={
                        "top": "12mm",
                        "right": "12mm",
                        "bottom": "12mm",
                        "left": "12mm",
                    },
                )
            finally:
                browser.close()
    except Exception as exc:
        # Never bubble up browser internals or report text in API errors.
        raise PdfExportUnavailable(
            "Chromium could not render the report. Install the Playwright Chromium browser and retry."
        ) from exc
    return data
