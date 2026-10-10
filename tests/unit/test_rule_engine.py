from pathlib import Path

from app.parsing.dispatcher import parse_document
from app.rules.engine import run_rules
from app.rules.loader import load_ruleset
from app.schemas.document import NormalizedDocument

ROOT = Path(__file__).resolve().parents[2]


def test_engine_runs_available_rules_and_marks_example_ruleset_unverified():
    ruleset = load_ruleset(ROOT / "rulesets" / "mazandaran_engineering_example.yaml")
    document = NormalizedDocument(
        source_format="docx",
        file_name="empty.docx",
        elements=[],
        parsing_complete=True,
    )
    report = run_rules(document, ruleset)
    assert report.ruleset_verified is False
    assert "نمونه" in report.disclaimer_fa
    assert report.rules_checked > 0
    assert report.rules_skipped > 0
    assert len(report.results) == len(ruleset.rules)


def test_fixture_report_contains_evidence_bearing_findings():
    ruleset = load_ruleset(ROOT / "rulesets" / "mazandaran_engineering_example.yaml")
    # Fixture generation is an autouse test-session fixture.
    content = (ROOT / "tests" / "fixtures" / "synthetic_bad.docx").read_bytes()
    document = parse_document("synthetic_bad.docx", content, max_size_bytes=30 * 1024 * 1024)
    report = run_rules(document, ruleset)
    assert report.ruleset_verified is False
    assert report.findings
    assert all(item.rule_id and item.title_en for item in report.findings)
    assert all(item.snippet or item.element_id is None for item in report.findings)
    assert any(item.rule_id == "REFERENCES_CROSSCHECK" for item in report.findings)
