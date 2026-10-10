# ThesisCheck — Persian-first thesis review

ThesisCheck is a draft-review and format-control assistant for graduate theses. It aims to help students find formatting, citation, terminology and structure issues before supervisor review. It does not generate thesis sections for submission, fabricate references, or silently rewrite original text.

> **Current status: Phase 1 document-inspection foundation.** The app can validate and parse DOCX files and perform best-effort text extraction from PDFs. It shows a parser summary and diagnostics. Citation analysis, official formatting checks, the health score, report exports, authentication and payments are not implemented yet.

## Implemented

- Persian RTL landing page with a DOCX/PDF inspection form.
- FastAPI POST endpoint at /api/v1/inspect and /health check.
- In-memory upload processing; the endpoint does not persist uploaded files or call an LLM.
- Extension and signature validation, configurable size limit, DOCM rejection, DOCX ZIP entry/decompressed-size/compression-ratio limits, and macro-payload rejection.
- DOCX heading/paragraph/table extraction, paragraph/run formatting hints, complex-script font hints, section/page setup and header/footer page-field metadata.
- Best-effort PDF text extraction with page locations and explicit warnings about unavailable style checks and scanned PDFs.
- Stable element IDs, normalized comparison text and parser diagnostics.
- Synthetic test fixtures and CI checks.

## Important limitations

- The ruleset at rulesets/mazandaran_engineering_example.yaml is explicitly **unverified example configuration**, not the official University of Mazandaran guideline. Do not claim official compliance until the actual guideline is supplied and encoded.
- DOCX page numbers cannot be reliably calculated by python-docx; findings use source IDs and heading paths. PDF extraction can mis-order multi-column, formula-rich or mixed RTL/LTR material.
- Scanned PDFs are detected as lacking a text layer. OCR is not implemented.
- DOCX footnotes/endnotes and embedded drawing/equation internals are not fully extracted. The parser reports known limitations.
- The inspection route is for local/demo use, not an internet-exposed production service. An isolated worker, persistent jobs, authentication, rate limits and deployment hardening remain future work.

## Requirements

- Python 3.12+
- Optional: Docker and Docker Compose

## Run locally

    python -m venv .venv
    # Windows PowerShell:
    .\.venv\Scripts\Activate.ps1
    # macOS/Linux:
    # source .venv/bin/activate

    python -m pip install --upgrade pip
    pip install -e ".[dev]"
    uvicorn app.main:app --reload

Open http://127.0.0.1:8000. Interactive API documentation is at http://127.0.0.1:8000/docs.

## Run tests and lint

    pytest
    ruff check .

Regenerate the synthetic DOCX fixtures with:

    python scripts/generate_fixtures.py

All fixture content is fictional and must not be treated as a real publication or citation.

## Docker

    cp .env.example .env
    # Windows PowerShell: Copy-Item .env.example .env
    docker compose up --build

The initial container runs the inspection demo. Do not expose it as a production file-processing service before the remaining security and operational work is implemented.

## Privacy draft (Persian)

«در مرحله فعلی، فایل برای استخراج ساختار در حافظه موقت پردازش می‌شود و برنامه آن را در ذخیره‌سازی دائمی نگه نمی‌دارد. فقط خلاصه‌ای از ساختار شناسایی‌شده و چند نمونه محدود از متن به مرورگر بازگردانده می‌شود. در این نسخه از سرویس بیرونی هوش مصنوعی استفاده نمی‌شود. نسخه‌های آینده باید سیاست نگهداری، حذف دستی و ارسال احتمالی متن به ارائه‌دهنده بیرونی را شفاف اعلام کنند.»

## Planned phases

See PLAN.md. The next stage adds deterministic rule checkers and evidence-backed issues after parsing has been verified.

## Disclaimer

ThesisCheck is a draft-review aid, not an academic grade, plagiarism verdict, verified-source service, or guarantee of compliance.
