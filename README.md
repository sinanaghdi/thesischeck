# ThesisCheck — Persian-first thesis review

ThesisCheck is a draft-review and format-control assistant for graduate theses. It helps identify potential formatting, citation, terminology, abstract and structure issues before supervisor review. It does not generate thesis sections for submission, fabricate references, or silently rewrite source text.

> **Current status: Phase 7 slice 7 — loopback-only Nginx edge with request limits and streamed proxying.** The app accepts DOCX/PDF for in-memory inspection, runs deterministic offline checks, produces a coverage-aware provisional score, and exports JSON and self-contained RTL HTML. PDF export uses optional Playwright/Chromium.

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
- Hardened Docker profile with distinct web and parser-service containers on an internal network. Both run non-root with read-only root filesystems and resource limits; parser has no published host port or outbound network route.

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

Generate both the parser token and the local demo login credentials. The Docker Compose profile **requires** a username and a password with at least 24 characters; the example password is intentionally blank and is not a usable credential.

    python -c "import secrets; print(secrets.token_urlsafe(48))"

Paste one generated value after `PARSER_SERVICE_TOKEN=` and another after `THESISCHECK_BASIC_AUTH_PASSWORD=` in `.env`. Keep `THESISCHECK_BASIC_AUTH_USERNAME` as your desired login name. The Docker web app enables a shared HTTP Basic Auth gate; your browser will show its native username/password prompt. The `/health` route remains available for container health checks.

This is a single shared demo credential, not individual user accounts, authorization roles, password reset, or a production identity system. Protect the `.env` file and never commit it.

Keep `DEBUG=false` and replace the placeholder `JWT_SECRET` with a strong random value before sharing the environment file. Start the local demo:

    docker compose up --build

The Compose profile publishes only the Nginx edge on `127.0.0.1:8000`. The web API has no host-published port and is reachable through the internal edge network; the parser is attached only to its own internal network and has no published port or outbound route. Both application containers are read-only, resource-limited and run without added Linux capabilities.

The Nginx edge enforces a request-body cap, per-source-IP rate limiting and concurrent-connection limiting for file inspection/report routes, connection/read timeouts, and streaming proxying without request-body disk buffering. Its default request limit is 31 MiB (30 MiB upload plus multipart overhead); if you change `MAX_UPLOAD_MB`, update `client_max_body_size` in `deploy/nginx.conf` to at least the configured file limit plus multipart overhead. The web app's own raw-body guard and file-size validation remain in place.

The web app sends raw document bytes to `http://parser:8001/internal/parse` with the shared token. The parser service checks that token using a constant-time comparison, applies its own raw-body limit, and invokes the supervised parsing subprocess. It receives no database, JWT or LLM configuration and does not persist inputs or normalized results.

These are layered defenses, not an absolute sandbox: the containers share the host kernel, and the parser can contact its web peer on the private network. The configured Nginx shared zone rate limits requests at this single edge instance; horizontally scaled edge instances would need coordinated/shared enforcement. Per-user accounts and role-based authorization, a production trusted-edge setup, retention policy if persistence is introduced, and target-environment security/load acceptance remain open.

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

- `INSPECTION_RATE_LIMIT` and `INSPECTION_RATE_WINDOW_SECONDS` configure the process-local application limiter. In Compose, Nginx also applies per-source-IP shared-zone rate and connection limits before the request reaches the application. The app deliberately does not trust forwarded-IP headers; the edge is the only route to the web container.
- Rate-limit state is held in process memory, so it is not shared across multiple workers or replicas. Put a shared rate limiter at the trusted reverse proxy before exposing the service publicly.
- Inspection/report responses use `Cache-Control: no-store` and `Pragma: no-cache`; baseline `nosniff`, referrer-policy and frame-denial headers are set. Unexpected processing exceptions return a generic 500 message, while known parser failures return a controlled 422 message.
- These guardrails do **not** make file parsing safe for unrestricted public traffic. A truly isolated container/worker identity, request-body limits at the edge, authentication/authorization, shared rate limiting, fuzz testing, retention/deletion workflows and load testing are still required before public deployment.

## Request-body limits

- The ASGI guard checks declared `Content-Length` before multipart parsing and counts incoming chunks when that header is absent or understated. It returns HTTP 413 with a stable error code and does not buffer the whole request body in its own middleware.
- The body cap is `MAX_UPLOAD_MB * 1 MiB + 1 MiB` for multipart framing and fields. The separate parser validation still caps the uploaded file bytes at `MAX_UPLOAD_MB`.
- Configure the same or a stricter body-size cap at the trusted reverse proxy/server edge; this application middleware is defense in depth, not a replacement for network-edge limits.

## Parser worker boundary

- `PARSER_BACKEND=subprocess` is the local-development default; Compose overrides it to `service`. `PARSER_SERVICE_TIMEOUT_SECONDS` defaults to 45 seconds for the web-to-parser request. `PARSER_WORKER_TIMEOUT_SECONDS` defaults to 35; `PARSER_WORKER_CPU_SECONDS` defaults to 25 where POSIX CPU limits are available; `PARSER_WORKER_MEMORY_MB` defaults to 1024 where POSIX address-space limits are available; `PARSER_WORKER_CONCURRENCY` defaults to 2 per parser-service process.
- The worker receives the source bytes through stdin, emits a validated JSON document over stdout, runs from the system temporary directory, and does not inherit application secrets in its environment. Timeout, busy and abnormal-worker failures return controlled API errors.
- With local `subprocess` mode, the child shares the app's OS identity. In Compose, the web API calls a distinct parser-service container that invokes the supervised child within its own container. The parser has no host-published port, receives no DB/JWT/LLM settings and has no outbound route. Both containers still share the host kernel, and the parser can reach its web peer over the private network. POSIX child limits are platform-dependent; Windows does not provide these `resource` limits. **This is defense in depth, not a complete security sandbox.** Public deployment still requires trusted-edge controls and independent security/load-test acceptance.

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
- The inspection route remains for local/demo use. The Docker profile includes a shared Basic Auth gate for the demo; it is not per-user authentication or role-based authorization. Per-user accounts, shared rate limiting across edge replicas, retention/deletion policy if persistence is introduced, and target-environment load/security testing are required before public deployment.

## Privacy notice draft (Persian)

«در نسخه فعلی، فایل برای استخراج ساختار و اجرای قواعد قطعی در حافظه موقت پردازش می‌شود و در ذخیره‌سازی دائمی برنامه نگه‌داری نمی‌شود. متن کامل سند در لاگ‌ها ثبت نمی‌شود؛ خلاصه، یافته‌ها و شواهد کوتاه به کاربر نمایش داده می‌شوند. در این نسخه از سرویس بیرونی هوش مصنوعی استفاده نمی‌شود. خروجی گزارش در پاسخ همان درخواست تولید می‌شود و روی سرور ذخیره دائمی نمی‌شود.»

## Disclaimer

ThesisCheck is a draft-review aid, not an academic grade, plagiarism verdict, verified-source service, or guarantee of compliance.
