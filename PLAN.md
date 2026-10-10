# ThesisCheck implementation plan

## Status

- [x] Phase 0: foundation, normalization, rule schema/loader, basic UI, health endpoint, synthetic fixture generator, tests and CI.
- [x] Phase 1: safe upload validation, DOCX/PDF parsing, normalized document model, parser diagnostics and inspection-summary API.
- [x] Phase 2: initial deterministic rule registry, reference/citation heuristics, editable terminology glossary, abstract checks, figure/table cross-reference checks, heading hierarchy hints and report findings in the UI.
- [x] Phase 3: coverage-aware provisional scoring, category breakdowns, executive summary, prioritized findings, downloadable HTML/JSON and optional Chromium PDF export.
- [ ] Phase 3 follow-up: bundle a licensed Persian-capable font and visually test PDF on Windows/Linux; add export visual-regression tests.
- [ ] Phase 4: professor-demo report polish, issue filters, report comparison and parsing-coverage UX.
- [ ] Phase 5: optional LLM provider, chapter chunking, strict structured output, evidence validation and cost estimates.
- [ ] Phase 6: accounts, authorization, plan gates, admin rules/glossary management and mock payments.
- [ ] Phase 7: isolated parsing worker, retention/deletion workflows, rate limiting, fuzz/security tests, 100-page performance benchmark and production deployment acceptance.

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
- PDF export requires the optional Playwright package and installed Chromium. The renderer uses locally installed fonts; no font binary is bundled in this phase, so verify PDF shaping on the target environment.
- The example Mazandaran ruleset remains unverified; official formatting compliance cannot be claimed.
