# ThesisCheck implementation plan

## Status

- [x] Phase 0: foundation, normalization, rule schema/loader, basic UI, health endpoint, synthetic fixture generator, tests and CI.
- [x] Phase 1: safe upload validation, DOCX/PDF parsing, normalized document model, parser diagnostics and inspection-summary API.
- [ ] Phase 1 acceptance follow-up: isolate parsing in a restricted worker and add deeper malformed-file/resource-exhaustion tests before public deployment.
- [ ] Phase 2: deterministic rule engine, references, terminology, abstracts, figure/table, formatting and structure checks.
- [ ] Phase 3: report schema, transparent scoring, prioritization, HTML/JSON/PDF export.
- [ ] Phase 4: polished Persian-first demo flow and detailed report screens.
- [ ] Phase 5: optional LLM provider, chunking, strict structured outputs and evidence verification.
- [ ] Phase 6: accounts, authorization, plan gates, admin rule/glossary management and mock payments.
- [ ] Phase 7: security/fuzz testing, 100-page performance benchmark and deployment acceptance.

## Architecture decisions

- FastAPI + Jinja2 + locally hosted CSS/JavaScript.
- SQLAlchemy 2.x + Alembic; SQLite initially, configurable URL for PostgreSQL.
- A separate persistent database-backed analysis worker before introducing Redis/Celery.
- DOCX: python-docx plus lxml/OOXML for headings, paragraph/table order, selected run formatting, complex-script font attributes, section setup and header/footer page fields. PDF: pdfplumber text extraction, with OCR unavailable initially.
- NLP: Unicode normalization, regex and rapidfuzz; avoid heavier dependencies unless demonstrated useful.
- AI: provider abstraction, off by default, mock provider for tests.
- PDF report: Playwright/Chromium with a bundled licensed Persian-capable font, followed by RTL visual tests.

## Phase 1 acceptance results

- Extension/signature/size checks reject unsupported and malformed uploads.
- DOCM and macro-marked DOCX packages are rejected.
- DOCX parsing preserves body-level paragraph/table order and supplies source element IDs, heading paths, run hints, section setup and parser diagnostics.
- PDF parsing provides page locations and explicit warnings for missing text layer and unavailable DOCX-level formatting checks.
- The API returns a bounded summary (up to 50 headings and five short text previews), not the complete extracted document.
- Upload data is processed in memory by the inspection endpoint, is not persistently saved, and is not sent to an LLM.
- The current suite has 24 passing tests in the local run. CI is the merge gate for the branch.

## Known limits

- No actual official Mazandaran thesis guideline has been supplied.
- A synchronous inspection endpoint exists; a restricted worker, authentication, persistent jobs, retention/deletion workflows, rate limiting, full reporting and payments are not implemented yet.
- No font binary is bundled until license and PDF shaping are validated.
- Scanned PDF OCR, DOCX page-number mapping, footnote/endnote extraction and complex drawing/equation interpretation remain unavailable or partial.
