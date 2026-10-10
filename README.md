# ThesisCheck — Phase 0 Foundation

ThesisCheck (working name; Persian name candidate: **PayanNegar / پایان‌نگار**) is a Persian-first writing-quality and format-control assistant for graduate theses. It helps students find consistency, formatting, citation, and structure issues before supervisor review. It does not write thesis sections for submission, invent references, or silently rewrite source documents.

> **Current status: Phase 0 scaffold.** This repository is not yet a functioning thesis analyzer. The home page and health endpoints run; rule configuration, Persian normalization, the normalized document model, test fixtures, and the initial test suite are foundations for later phases. Upload handling and analysis are not enabled in this phase.

## Product principles

- Findings should be evidence-based and distinguish confirmed defects from heuristics and unverifiable information.
- Suggestions must remain separate from the original document.
- No external AI calls are required. AI will be optional and provider-swappable.
- Uploaded document text must not be written to application logs or used for model training.
- University-specific formatting checks must use an explicitly versioned ruleset.
- `rulesets/mazandaran_engineering_example.yaml` contains illustrative placeholders only. It is **not** an official University of Mazandaran guideline.

## Requirements

- Python 3.12+
- Optional: Docker and Docker Compose

## Run locally

```bash
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

python -m pip install --upgrade pip
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`. The current UI intentionally states that analysis is not yet enabled.

## Run tests

```bash
pytest
```

Regenerate clearly synthetic fixture documents:

```bash
python scripts/generate_fixtures.py
```

Fixtures are test artifacts and contain fictional text. They must never be interpreted as real scientific sources or reference recommendations.

## Docker

```bash
cp .env.example .env
# On Windows PowerShell: Copy-Item .env.example .env
docker compose up --build
```

The initial container runs the web scaffold. A separate persistent analysis worker, upload sandboxing, database migrations and report exports are planned in later phases; do not expose this scaffold as a production document-processing service.

## Configuration

Configuration is environment-variable based. Start with `.env.example`. Never commit real API keys, JWT secrets, uploaded theses, or private reports. `LLM_MODE=off` is the default and must remain a supported mode.

## Planned phases

See [PLAN.md](PLAN.md). Phase 0 focuses on a reproducible project foundation and test fixtures. Deterministic parsing and checkers come before LLM-assisted analysis.

## Privacy notice draft (Persian)

«در نسخه نهایی، فایل پایان‌نامه فقط برای اجرای بررسی‌های درخواستی استفاده می‌شود. متن فایل در لاگ‌های برنامه ثبت نمی‌شود. نگهداری و حذف فایل‌ها مطابق تنظیمات اعلام‌شده انجام خواهد شد. در صورت فعال‌سازی تحلیل‌گر بیرونی هوش مصنوعی، بخش‌های لازم از متن ممکن است برای همان سرویس ارسال شود؛ پیش از ارسال، ارائه‌دهنده و سیاست نگهداری داده به کاربر اعلام خواهد شد. این نسخه اولیه هنوز قابلیت بارگذاری یا تحلیل فایل را فعال نکرده است.»

## Disclaimer

ThesisCheck is a draft-review aid, not an academic grade, plagiarism verdict, citation verification service, or guarantee of compliance. Official faculty requirements must be supplied and verified before format results can be called compliant.
