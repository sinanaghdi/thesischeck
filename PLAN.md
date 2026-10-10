# ThesisCheck implementation plan

## Status

- [x] Phase 0: foundation, normalization, rule schema/loader, basic UI, health endpoint, synthetic fixture generator, tests and CI.
- [ ] Phase 1: safe upload validation, DOCX/PDF parsing, normalized document model, parsing diagnostics.
- [ ] Phase 2: deterministic rule engine, references, terminology, abstracts, figure/table, formatting and structure checks.
- [ ] Phase 3: report schema, transparent scoring, prioritization, HTML/JSON/PDF export.
- [ ] Phase 4: polished Persian-first demo upload flow and report screens.
- [ ] Phase 5: optional LLM provider, chunking, strict structured outputs and evidence verification.
- [ ] Phase 6: accounts, authorization, plan gates, admin rule/glossary management and mock payments.
- [ ] Phase 7: security/fuzz testing, 100-page performance benchmark and deployment acceptance.

## Architecture decisions

- FastAPI + Jinja2 + locally hosted CSS/JavaScript.
- SQLAlchemy 2.x + Alembic; SQLite initially, configurable URL for PostgreSQL.
- A separate persistent database-backed analysis worker before introducing Redis/Celery.
- DOCX: python-docx plus lxml/OOXML. PDF: pdfplumber, with OCR unavailable initially.
- NLP: Unicode normalization, regex and rapidfuzz; avoid heavier dependencies unless demonstrated useful.
- AI: provider abstraction, off by default, mock provider for tests.
- PDF report: Playwright/Chromium with a bundled licensed Persian-capable font, followed by RTL visual tests.

## Phase 0 acceptance criteria

- App starts without a remote CDN; /health and home page respond.
- Ruleset schema validation and Persian character/digit normalization are tested.
- Synthetic DOCX fixture generator and tests run in CI.
- Mazandaran example ruleset prominently states it is unverified.
- No thesis uploads are accepted in this scaffold.

## Known limits

- No upload/analysis routes, parser, worker, report engine, accounts or payments yet.
- No official Mazandaran guideline has been supplied.
- No font binary is bundled until license and PDF shaping are validated.
