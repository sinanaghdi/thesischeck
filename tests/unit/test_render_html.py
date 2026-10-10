from pathlib import Path

from app.reports.render_html import render_html_report
from app.reports.scoring import build_health_report
from app.rules.engine import run_rules
from app.rules.loader import load_ruleset
from app.schemas.document import NormalizedDocument

ROOT = Path(__file__).resolve().parents[2]


def test_html_report_is_interactive_and_escapes_untrusted_file_names():
    ruleset = load_ruleset(ROOT / "rulesets" / "mazandaran_engineering_example.yaml")
    document = NormalizedDocument(
        source_format="docx",
        file_name="draft.docx",
        elements=[],
        parsing_complete=True,
    )
    checks = run_rules(document, ruleset)
    report = build_health_report(document, checks, ruleset)
    report.file_name = '<img src=x onerror="alert(99)">.docx'

    html = render_html_report(report)

    assert 'lang="fa" dir="rtl"' in html
    assert 'id="finding-search"' in html
    assert 'id="finding-severity"' in html
    assert "&lt;img src=x onerror=&quot;alert(99)&quot;&gt;" in html
    assert '<img src=x onerror="alert(99)">' not in html
    assert "وزن سنجیده‌شده" in html
