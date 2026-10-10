# ThesisCheck — Persian-first thesis review

ThesisCheck is a draft-review and format-control assistant for graduate theses. It helps identify potential formatting, citation, terminology, abstract and structure issues before supervisor review. It does not generate thesis sections for submission, fabricate references, or silently rewrite source text.

> **Current status: Phase 2 — initial deterministic checkers.** The app accepts DOCX/PDF for in-memory inspection, returns a bounded parsing summary, and runs selected offline rules for citation/reference consistency, terminology variants, bilingual abstract structure, figure/table cross-references, and heading hierarchy. The results are heuristic review suggestions, not an academic grade or a verification of scientific truth.

## Implemented

- Persian RTL upload-and-inspection interface.
- FastAPI POST endpoint at /api/v1/inspect and /health.
- In-memory upload validation and DOCX/PDF extraction. No upload is written to permanent storage or sent to an LLM.
- Extension/signature/size checks, DOCM rejection, DOCX ZIP limits and macro payload rejection.
- DOCX headings, body paragraph/table order, selected run/font/RTL properties, section setup and parser diagnostics.
- Best-effort PDF text extraction with page locations and explicit warnings when layout/style checks are unavailable.
- Rule registry with localized findings, evidence snippets, confidence hints, and rule execution states.
- Offline citation/reference checks: numeric groups/ranges, citation-to-list mismatches, duplicated numbers, numbering gaps, probable duplicates, incomplete-looking entries and heuristic APA/numeric-style mixing.
- Glossary-based Persian terminology variant detection using an editable CSV.
- Heuristic checks for abstract presence, keyword-count mismatch, approximate length/numeric discrepancies, figure/table captions, dangling references and heading-level jumps.
- Synthetic DOCX fixtures generated during tests and GitHub Actions for pytest + Ruff.

## Limitations and safety boundaries

- The ruleset at rulesets/mazandaran_engineering_example.yaml is **unverified example configuration**, not the official University of Mazandaran guideline. Formatting rules that need official fonts/margins/spacing are disabled until valid values are supplied.
- Citation parsing uses heuristics. A missing match does not prove a reference is invalid, and similarity does not prove a duplicate. No citation, DOI, page number or venue is fabricated.
- The current score is not implemented. Checks marked passed mean only “no issue found by this rule”; they do not prove compliance.
- DOCX page numbers cannot be reliably computed by python-docx; source IDs and heading paths are used. PDF extraction may mis-order columns, formulas, and mixed RTL/LTR content.
- Scanned PDF OCR, complete footnote/endnote extraction, full equation/drawing interpretation, semantic abstract translation matching, AI traceability, PDF report export, auth, billing and accounts are not implemented.
- The inspection route is for local/demo use, not an internet-exposed production service. Parsing worker isolation, persistent jobs, authentication, rate limits and additional resource-exhaustion hardening remain required before public deployment.

## Requirements and local run

- Python 3.12+
- Optional: Docker and Docker Compose

    python -m venv .venv
    # Windows PowerShell:
    .\.venv\Scripts\Activate.ps1
    # macOS/Linux:
    # source .venv/bin/activate

    python -m pip install --upgrade pip
    pip install -e ".[dev]"
    uvicorn app.main:app --reload

Open http://127.0.0.1:8000. Interactive API docs: http://127.0.0.1:8000/docs.

## Tests and lint

    pytest
    ruff check .

The synthetic fixture generator is scripts/generate_fixtures.py. Fixture content is fictional and must not be treated as a real publication or citation.

## Docker

    cp .env.example .env
    # Windows PowerShell: Copy-Item .env.example .env
    docker compose up --build

Do not expose the demo as a production file-processing service until the remaining security and operational work is completed.

## Privacy notice draft (Persian)

«در نسخه فعلی، فایل برای استخراج ساختار و اجرای قواعد قطعی در حافظه موقت پردازش می‌شود و در ذخیره‌سازی دائمی برنامه نگه‌داری نمی‌شود. متن کامل سند در لاگ‌ها ثبت نمی‌شود؛ خلاصه‌ای از ساختار، چند نمونه محدود از متن و شواهد کوتاه یافته‌ها به کاربر نمایش داده می‌شود. در این نسخه از سرویس بیرونی هوش مصنوعی استفاده نمی‌شود. نسخه‌های آینده باید سیاست نگهداری، حذف دستی و ارسال احتمالی متن به ارائه‌دهنده بیرونی را پیش از ارسال شفاف اعلام کنند.»

## Disclaimer

ThesisCheck is a draft-review aid, not an academic grade, plagiarism verdict, verified-source service, or guarantee of compliance.
