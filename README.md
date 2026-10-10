# ThesisCheck — Persian-first thesis review

ThesisCheck is a draft-review and format-control assistant for graduate theses. It helps identify potential formatting, citation, terminology, abstract and structure issues before supervisor review. It does not generate thesis sections for submission, fabricate references, or silently rewrite source text.

> **Current status: Phase 3 — scoring and report exports.** The app accepts DOCX/PDF for in-memory inspection, runs deterministic offline checks, produces a coverage-aware provisional score, and exports machine-readable JSON and self-contained RTL HTML. PDF export uses optional Playwright/Chromium.

## Implemented

- Persian RTL upload-and-inspection interface.
- FastAPI POST endpoint at /api/v1/inspect and POST /api/v1/report?format=json|html|pdf, plus /health.
- In-memory upload validation and DOCX/PDF extraction. No upload is written to permanent storage or sent to an LLM.
- DOCX headings, body paragraph/table order, selected run/font/RTL properties, section setup and parser diagnostics.
- Best-effort PDF text extraction with page locations and explicit warnings when layout/style checks are unavailable.
- Deterministic checker registry with localized findings, source evidence, severity, confidence and per-rule statuses.
- Offline citation/reference checks, editable glossary-based terminology checks, abstract structure checks, figure/table cross-reference checks and heading-hierarchy hints.
- Explainable provisional score with visible penalties, configured/assessed category weights, normalized weights and coverage. Skipped and unimplemented checks do not silently count as successful coverage.
- Self-contained HTML report with a one-page executive summary, score formula, category table, prioritized top issues, all findings and parsing limitations.
- JSON report export for later integrations.
- Optional Playwright/Chromium PDF export through the same RTL HTML renderer.
- Synthetic DOCX fixtures generated during tests and GitHub Actions for pytest + Ruff.

## Run locally

Requirements: Python 3.12+. Optional: Docker and Docker Compose.

    python -m venv .venv
    # Windows PowerShell:
    .\.venv\Scripts\Activate.ps1
    # macOS/Linux:
    # source .venv/bin/activate
    python -m pip install --upgrade pip
    pip install -e ".[dev]"
    uvicorn app.main:app --reload

Open http://127.0.0.1:8000. Interactive API docs: http://127.0.0.1:8000/docs.

## PDF export (optional)

Install the extra and its local Chromium browser:

    pip install -e ".[dev,pdf]"
    python -m playwright install chromium

PDF export does not use a CDN. Chromium provides Arabic-script shaping and browser RTL layout; the renderer uses locally installed Persian-capable fonts where available, such as Tahoma, Noto Naskh Arabic or DejaVu Sans. **A licensed font binary is not bundled yet**, so verify the rendered PDF on the actual demo machine before presenting it. If Playwright or Chromium is unavailable, the endpoint returns a clear 503 error; JSON and HTML exports do not depend on it.

The PDF extra increases the install footprint. For slim/container deployments that do not install the extra, JSON and HTML report exports remain available.

## API usage

Inspect a document and receive a bounded parsing summary plus the provisional score:

    curl -F "file=@draft.docx" http://127.0.0.1:8000/api/v1/inspect

Export JSON:

    curl -F "file=@draft.docx" "http://127.0.0.1:8000/api/v1/report?format=json" -o thesischeck-report.json

Export self-contained HTML:

    curl -F "file=@draft.docx" "http://127.0.0.1:8000/api/v1/report?format=html" -o thesischeck-report.html

Export PDF after installing the optional browser:

    curl -F "file=@draft.docx" "http://127.0.0.1:8000/api/v1/report?format=pdf" -o thesischeck-report.pdf

## Tests and lint

    pytest
    ruff check .

Synthetic fixture generator: scripts/generate_fixtures.py. Fixture content is fictional and must not be treated as a real publication or citation.

## Important limitations and safety boundaries

- rulesets/mazandaran_engineering_example.yaml is **unverified example configuration**, not the official University of Mazandaran guideline. Formatting rules that require official fonts, margins, spacing or required headings are disabled/skipped until valid values are supplied.
- The score is **not an academic grade** or a guarantee of scientific quality. Formula: category score = max(0, 100 - errors×12 - warnings×4 - info×1). Category weight is prorated to the share of configured rules that actually ran; the overall score is the weighted mean of assessed categories only. The report exposes both weighted coverage and unassessed categories.
- Citation/reference parsing is heuristic. Missing matches do not prove an invalid source, and similarity does not prove duplication. No citation, DOI, venue or page number is fabricated.
- DOCX page numbers cannot be reliably computed by python-docx; source IDs and heading paths are used. PDF extraction may mis-order columns, formulas and mixed RTL/LTR content. Scanned-PDF OCR and complete footnote/equation extraction are not implemented.
- Research traceability, LLM-assisted writing checks, user accounts, payments and persistent job management are not implemented.
- The inspection route remains for local/demo use. Isolated parsing workers, authentication, rate limiting and additional resource-exhaustion hardening are required before public deployment.

## Privacy notice draft (Persian)

«در نسخه فعلی، فایل برای استخراج ساختار و اجرای قواعد قطعی در حافظه موقت پردازش می‌شود و در ذخیره‌سازی دائمی برنامه نگه‌داری نمی‌شود. متن کامل سند در لاگ‌ها ثبت نمی‌شود؛ خلاصه، یافته‌ها و شواهد کوتاه به کاربر نمایش داده می‌شوند. در این نسخه از سرویس بیرونی هوش مصنوعی استفاده نمی‌شود. خروجی گزارش در پاسخ همان درخواست تولید می‌شود و روی سرور ذخیره دائمی نمی‌شود.»

## Disclaimer

ThesisCheck is a draft-review aid, not an academic grade, plagiarism verdict, verified-source service, or guarantee of compliance.
