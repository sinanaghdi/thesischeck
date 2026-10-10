# ThesisCheck implementation plan

## Status

- [x] Phase 0: foundation, normalization, rule schema/loader, basic UI, health endpoint, synthetic fixture generator, tests and CI.
- [x] Phase 1: safe upload validation, DOCX/PDF parsing, normalized document model, parser diagnostics and inspection-summary API.
- [x] Phase 2: initial deterministic rule registry, reference/citation heuristics, editable terminology glossary, abstract checks, figure/table cross-reference checks, heading hierarchy hints and report findings in the UI.
- [ ] Phase 2 follow-up: broaden citation-style fixtures, add adversarial parser resource tests, verify no unintended source text is logged, and improve checker confidence calibration.
- [ ] Phase 3: explainable health scoring, HTML/JSON/PDF report exports and issue prioritization.
- [ ] Phase 4: polished professor-demo report screens and parsing-coverage UX.
- [ ] Phase 5: optional LLM provider, chunking, structured outputs and evidence verification.
- [ ] Phase 6: accounts, authorization, plan gates, admin rule/glossary management and mock payments.
- [ ] Phase 7: isolated parsing worker, fuzz/security tests, 100-page performance benchmark and deployment acceptance.

## Architecture decisions

- FastAPI + Jinja2 + locally hosted CSS/JavaScript.
- SQLAlchemy 2.x + Alembic; SQLite initially, configurable URL for PostgreSQL.
- A separate persistent database-backed worker before introducing Redis/Celery.
- DOCX: python-docx plus lxml/OOXML; PDF: pdfplumber text extraction, OCR unavailable initially.
- NLP: Unicode normalization, regex and rapidfuzz; avoid heavier dependencies unless demonstrated useful.
- Deterministic rules are offline by default. Any AI work must be optional and provider-swappable.
- PDF report: Playwright/Chromium with a bundled licensed Persian-capable font, followed by RTL visual tests.

## Phase 2 guarantees and limits

- Rule sets are schema-validated and checker names resolve through an allowlisted registry, not dynamic imports.
- Per-rule state distinguishes passed, issue(s) found, and skipped/unconfigured.
- Findings have a source element ID and/or short quoted evidence, localized explanation/fix, category, severity and confidence.
- Citation/reference parsing is heuristic and offline. Probable duplicates and mismatches require human review; the system never fabricates bibliography data.
- The example Mazandaran profile remains unverified. Rules requiring official fonts, margins, spacing or required-heading lists stay disabled/skipped until properly configured.
- A passed check is not proof of academic or university compliance. Overall score and report exports are not implemented yet.
