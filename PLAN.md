# ThesisCheck implementation plan

## Status

- [x] Phase 0: foundation, normalization, rule schema/loader, basic UI, health endpoint, synthetic fixture generator, tests and CI.
- [x] Phase 1: safe upload validation, DOCX/PDF parsing, normalized document model, parser diagnostics and inspection-summary API.
- [x] Phase 2: initial deterministic rule registry, reference/citation heuristics, editable terminology glossary, abstract checks, figure/table cross-reference checks, heading hierarchy hints and report findings in the UI.
- [x] Phase 3: coverage-aware provisional scoring, category breakdowns, executive summary, prioritized findings, downloadable HTML/JSON and optional Chromium PDF export.
- [x] Phase 4 (slice 1): in-app finding filters and explicit parsing-coverage/limitations panel for the professor demo.
- [ ] Phase 4 follow-up: full English UI toggle, report-to-report comparison and visual QA of generated PDFs on target machines.
- [ ] Phase 5: optional LLM provider, chapter chunking, strict structured output, evidence validation and cost estimates.
- [ ] Phase 6: accounts, authorization, plan gates, admin rules/glossary management and mock payments.
- [x] Phase 7 (slice 1): API request guardrails, process-local rate limiting, no-store/security headers, and sanitized unexpected processing errors.
- [x] Phase 7 (slice 2): supervised parser subprocess with wall-clock timeout, bounded worker slots, minimal environment and platform-dependent POSIX resource limits.
- [x] Phase 7 (slice 3): streaming raw request-body size guard before multipart parsing, including requests without a trustworthy Content-Length.
- [x] Phase 7 (slice 4): deterministic adversarial upload regressions, malformed/conflicting Content-Length tests, parser-worker environment allowlist tests, and an opt-in 100-logical-page performance benchmark harness.
- [x] Phase 7 (slice 5): harden the local Docker runtime with loopback-only port publishing, read-only root filesystem, bounded temporary storage/resources, no-new-privileges, dropped capabilities and Uvicorn concurrency limits.
- [ ] Phase 7 follow-up: run benchmark on the intended deployment host, add property-based fuzzing if the dependency budget permits, move parsing to a separately constrained worker/container identity with no network access, add trusted-edge body limits and shared rate limiting, define retention/deletion behavior if persistence is introduced, and complete production acceptance tests.

## Architecture decisions

- FastAPI + Jinja2 + locally hosted CSS/JavaScript.
- SQLAlchemy 2.x + Alembic; SQLite initially, configurable URL for PostgreSQL.
- A separate persistent database-backed worker before introducing Redis/Celery.
- DOCX: python-docx plus lxml/OOXML; PDF: pdfplumber text extraction, OCR unavailable initially.
- NLP: Unicode normalization, regex and rapidfuzz.
- Deterministic rules are offline by default. Any AI work must be optional and provider-swappable.
- PDF reports: self-contained RTL HTML rendered by Playwright/Chromium (optional dependency), with local font fallback. Bundle a licensed Persian-capable font before claiming cross-machine PDF fidelity.

## Phase 3 scoring and reporting guarantees

- Score penalties are visible: error=12, warning=4, info=1; category score is clamped at zero.
- Assessed weight is proportional to executed rules within a configured scoring category. Skipped/unimplemented rules do not create coverage.
- Overall score is the weighted mean of assessed categories; weighted coverage and unavailable categories are shown.
- The score is a draft-review signal, not an academic grade, plagiarism result or proof of university compliance.
- HTML is self-contained, RTL and escaped against injected thesis text. JSON is machine-readable.
- PDF export requires optional Playwright and installed Chromium. No font binary is bundled yet, so verify shaping on the target environment.
- The example Mazandaran ruleset remains unverified; official formatting compliance cannot be claimed.
- API guardrails, request-body cap and parser subprocess supervision are a local/demo baseline, not a complete security boundary: rate limits are process-local, the child shares the host user's privileges, and public exposure still requires a sandboxed worker/container and trusted-edge controls.

## Phase 4 demo UX

- In-app filters support severity, category, free-text search, and one-click reset.
- Parsing coverage and parser limitations remain visually distinct from quality findings.
- Findings continue to show their evidence, category, confidence hint and source location; filtering does not modify the source document.


## Phase 7 slice 4 validation boundaries

- Adversarial tests are deterministic regression tests, not a substitute for continuous fuzzing or third-party security review.
- The large-document benchmark runs on demand and is intentionally excluded from CI due to noisy shared-runner timing. Its JSON output should be retained with deployment/benchmark notes when tested on the intended host.
- No public-production readiness is claimed until the parser has a separate constrained OS/container identity and the remaining trusted-edge, retention, and load-test requirements are addressed.


## Phase 7 slice 5 container boundary

- The Compose profile is designed for local/demo use and minimizes writable paths and process/resource exposure.
- The parser child still runs with the web container's unprivileged OS identity and retains container network access; this is not a separate sandbox.
- Port publishing defaults to loopback. Do not change it to a public interface until the separately isolated parser and trusted-edge controls exist.
