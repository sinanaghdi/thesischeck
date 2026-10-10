# ThesisCheck — Persian-first thesis review

ThesisCheck is a draft-review and format-control assistant for graduate theses. It helps identify potential formatting, citation, terminology, abstract and structure issues before supervisor review. It does not generate thesis sections for submission, fabricate references, or silently rewrite source text.

> **Current status: Phase 7 slice 5 — hardened local Docker runtime profile.** The app accepts DOCX/PDF for in-memory inspection, runs deterministic offline checks, produces a coverage-aware provisional score, and exports JSON and self-contained RTL HTML. PDF export uses optional Playwright/Chromium.

## Implemented

- Persian RTL upload-and-inspection interface.
- FastAPI POST endpoint at /api/v1/inspect, POST /api/v1/report?format=json|html|pdf, and /health.
- In-memory upload validation and DOCX/PDF extraction. No upload is written to permanent storage or sent to an LLM.
- DOCX headings, body paragraph/table order, selected run/font/RTL properties, section setup and parser diagnostics.
- Best-effort PDF text extraction with page locations and explicit warnings when layout/style checks are unavailable.
- Deterministic checker registry with localized findings, source evidence, severity, confidence and per-rule statuses.
- Offline citation/reference checks, editable glossary-based terminology checks, abstract structure checks, figure/table cross-reference checks and heading-hierarchy hints.
- Explainable provisional score with visible penalties, configured/assessed category weights, normalized weights and weighted coverage. Skipped and unimplemented checks do not count as successful coverage.
- Interactive, self-contained RTL HTML report with executive summary, score formula, category table, prioritized top issues, finding search/severity filters, all findings and parsing limitations.
- JSON report export and optional Playwright/Chromium PDF export.
- In-app finding filters for text, rule ID, severity and category.
- Parsing coverage panel that displays extracted element counts and parser limitations separately from thesis-quality findings.
- Per-process inspection/report rate limiting (configurable; default 20 requests per IP per 60 seconds), no-store API responses, baseline security headers, and sanitized unexpected errors.
- Supervised parser subprocess with a configurable wall-clock deadline, bounded concurrent worker slots, a minimal environment, and optional POSIX CPU/address-space/file-descriptor limits.
- Streaming raw-body cap on upload endpoints: max configured file size plus 1 MiB multipart overhead; oversized declared or streamed requests are rejected with HTTP 413 before document parsing.
- Synthetic DOCX fixtures generated during tests and GitHub Actions for pytest + Ruff.
- Hardened local Docker profile: non-root runtime user, loopback-only port binding, read-only container root filesystem, temporary filesystem for uploads, dropped Linux capabilities, no-new-privileges, CPU/memory/PID limits, and bounded Uvicorn concurrency.

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

## Hardened local Docker Compose profile

Create a local environment file and keep it out of Git:

    # Windows PowerShell
    Copy-Item .env.example .env
    # macOS/Linux
    # cp .env.example .env

Keep `DEBUG=false`; replace the placeholder `JWT_SECRET` with a strong random value before sharing the environment file, even though authentication is not implemented in this demo. Start the local demo:

    docker compose up --build

The Compose profile binds the web port to `127.0.0.1` only, runs as the unprivileged `appuser`, enables a read-only root filesystem, mounts a bounded `/tmp`, drops Linux capabilities, enables `no-new-privileges`, caps PIDs/CPU/memory, and limits Uvicorn to four concurrent connections. Uploaded multipart data may temporarily use `/tmp`; no persistent upload volume is configured.

These are container-level defense-in-depth settings, not proof that the parser is isolated. The parser subprocess still shares the web container's OS identity and network access. Do not expose this demo directly to the public internet; use a separately constrained parser worker/container plus trusted reverse-proxy limits and shared rate limiting first.

## PDF export (optional)

Install the extra and its local Chromium browser:

    pip install -e ".[dev,pdf]"
    python -m playwright install chromium

PDF export does not use a CDN. Chromium provides Arabic-script shaping and browser RTL layout; the renderer uses locally installed Persian-capable fonts where available, such as Tahoma, Noto Naskh Arabic or DejaVu Sans. A licensed font binary is not bundled yet, so verify the rendered PDF on the actual demo machine before presenting it. Without Playwright/Chromium, the PDF endpoint returns 503; JSON and HTML remain available.

## API usage

Inspect a document:

    curl -F "file=@draft.docx" http://127.0.0.1:8000/api/v1/inspect

Export JSON, self-contained HTML, or PDF:

    curl -F "file=@draft.docx" "http://127.0.0.1:8000/api/v1/report?format=json" -o thesischeck-report.json
    curl -F "file=@draft.docx" "http://127.0.0.1:8000/api/v1/report?format=html" -o thesischeck-report.html
    curl -F "file=@draft.docx" "http://127.0.0.1:8000/api/v1/report?format=pdf" -o thesischeck-report.pdf

PDF requires the optional browser installation above.

## API guardrails and deployment boundary

- `INSPECTION_RATE_LIMIT` and `INSPECTION_RATE_WINDOW_SECONDS` configure the process-local request limiter. The limiter applies to `POST /api/v1/inspect` and `POST /api/v1/report`; `429` responses include `Retry-After`. `X-Forwarded-For` is intentionally ignored because it is trustworthy only when set by a configured proxy.
- Rate-limit state is held in process memory, so it is not shared across multiple workers or replicas. Put a shared rate limiter at the trusted reverse proxy before exposing the service publicly.
- Inspection/report responses use `Cache-Control: no-store` and `Pragma: no-cache`; baseline `nosniff`, referrer-policy and frame-denial headers are set. Unexpected processing exceptions return a generic 500 message, while known parser failures return a controlled 422 message.
- These guardrails do **not** make file parsing safe for unrestricted public traffic. A truly isolated container/worker identity, request-body limits at the edge, authentication/authorization, shared rate limiting, fuzz testing, retention/deletion workflows and load testing are still required before public deployment.

## Request-body limits

- The ASGI guard checks declared `Content-Length` before multipart parsing and counts incoming chunks when that header is absent or understated. It returns HTTP 413 with a stable error code and does not buffer the whole request body in its own middleware.
- The body cap is `MAX_UPLOAD_MB * 1 MiB + 1 MiB` for multipart framing and fields. The separate parser validation still caps the uploaded file bytes at `MAX_UPLOAD_MB`.
- Configure the same or a stricter body-size cap at the trusted reverse proxy/server edge; this application middleware is defense in depth, not a replacement for network-edge limits.

## Parser worker boundary

- `PARSER_WORKER_TIMEOUT_SECONDS` defaults to 35; `PARSER_WORKER_CPU_SECONDS` defaults to 25 where POSIX CPU limits are available; `PARSER_WORKER_MEMORY_MB` defaults to 1024 where POSIX address-space limits are available; `PARSER_WORKER_CONCURRENCY` defaults to 2 per application process.
- The worker receives the source bytes through stdin, emits a validated JSON document over stdout, runs from the system temporary directory, and does not inherit application secrets in its environment. Timeout, busy and abnormal-worker failures return controlled API errors.
- The subprocess runs under the same OS user and can still access the host's files/network. POSIX limits are platform-dependent and Windows does not provide these `resource` limits. **This is process supervision, not a complete sandbox.** Public deployment still requires an isolated container/worker identity, no network access, secret separation, shared edge limits and resource controls at the OS/container level.

## Adversarial regression tests and performance benchmark

The automated suite includes deterministic malformed upload payloads, DOCX ZIP expansion/entry limits, extreme compression-ratio rejection, malformed or conflicting `Content-Length` headers, and a check that application secrets are not copied into the parser subprocess environment.

Run the opt-in 100-logical-page DOCX benchmark from the repository root:

    python -m scripts.benchmark_100_page_docx

The benchmark builds a fictional in-memory DOCX with explicit page breaks, measures the supervised parser path, prints a JSON summary, and exits nonzero when parse time exceeds the default 30-second threshold. Useful variants:

    python -m scripts.benchmark_100_page_docx --pages 100 --paragraphs-per-page 6 --max-seconds 30

The benchmark is not part of CI because shared-runner timings are noisy. Record results on the actual target environment before treating the threshold as an acceptance result. DOCX page layout varies by word processor and installed fonts; the reported page count is the requested logical-page count, not a guarantee of identical pagination in every editor.

## Tests and lint

    pytest
    ruff check .

Synthetic fixture generator: scripts/generate_fixtures.py. Fixture content is fictional and must not be treated as a real publication or citation.

## Important limitations and safety boundaries

- rulesets/mazandaran_engineering_example.yaml is unverified example configuration, not the official University of Mazandaran guideline. Formatting rules that require official fonts, margins, spacing or required headings are disabled/skipped until verified values are supplied.
- The score is not an academic grade or a guarantee of scientific quality. Category penalty formula: max(0, 100 - errors×12 - warnings×4 - info×1). Each category's assessed weight is prorated to configured rules that actually ran; the overall score is the weighted mean of assessed categories only. The report exposes weighted coverage and unassessed categories.
- Citation/reference parsing is heuristic. Missing matches do not prove an invalid source, and similarity does not prove duplication. No citation, DOI, venue or page number is fabricated.
- DOCX page numbers cannot be reliably computed by python-docx; source IDs and heading paths are used. PDF extraction may mis-order columns, formulas and mixed RTL/LTR content. Scanned-PDF OCR and complete footnote/equation extraction are not implemented.
- Research traceability, LLM-assisted writing checks, user accounts, payments and persistent job management are not implemented.
- The inspection route remains for local/demo use. The Compose profile is defense in depth only; a separate isolated parser worker/container identity, authentication, shared rate limiting at a trusted edge, request-body limits there, retention/deletion workflows and target-environment load testing are required before public deployment.

## Privacy notice draft (Persian)

«در نسخه فعلی، فایل برای استخراج ساختار و اجرای قواعد قطعی در حافظه موقت پردازش می‌شود و در ذخیره‌سازی دائمی برنامه نگه‌داری نمی‌شود. متن کامل سند در لاگ‌ها ثبت نمی‌شود؛ خلاصه، یافته‌ها و شواهد کوتاه به کاربر نمایش داده می‌شوند. در این نسخه از سرویس بیرونی هوش مصنوعی استفاده نمی‌شود. خروجی گزارش در پاسخ همان درخواست تولید می‌شود و روی سرور ذخیره دائمی نمی‌شود.»

## Disclaimer

ThesisCheck is a draft-review aid, not an academic grade, plagiarism verdict, verified-source service, or guarantee of compliance.
