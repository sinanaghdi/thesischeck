from pathlib import Path

from app.parsing.dispatcher import parse_document
from app.reports.scoring import build_health_report
from app.rules.engine import run_rules
from app.rules.loader import load_ruleset

ROOT = Path(__file__).resolve().parents[2]


def test_score_is_explainable_and_does_not_claim_full_coverage():
    ruleset = load_ruleset(ROOT / "rulesets" / "mazandaran_engineering_example.yaml")
    content = (ROOT / "tests" / "fixtures" / "synthetic_bad.docx").read_bytes()
    document = parse_document("synthetic_bad.docx", content, max_size_bytes=30 * 1024 * 1024)
    checks = run_rules(document, ruleset)
    report = build_health_report(document, checks, ruleset)

    assert report.score is not None
    assert 0 <= report.score <= 100
    assert 0 < report.coverage_percent < 100
    assert report.assessed_weight_total < report.configured_weight_total
    assert report.ruleset_verified is False
    assert "not an academic grade" in " ".join(report.limitations_en).lower()
    assert "skipped" in report.score_formula_en.lower()
    assert any(item.key == "writing_quality" and item.score is None for item in report.categories)
    assert sum(item.normalized_weight for item in report.categories) == 100.0


def test_report_keeps_top_issues_and_full_findings_consistent():
    ruleset = load_ruleset(ROOT / "rulesets" / "mazandaran_engineering_example.yaml")
    content = (ROOT / "tests" / "fixtures" / "synthetic_bad.docx").read_bytes()
    document = parse_document("synthetic_bad.docx", content, max_size_bytes=30 * 1024 * 1024)
    report = build_health_report(document, run_rules(document, ruleset), ruleset)

    assert report.top_issues == report.checks.findings[:10]
    assert all(0 <= item.confidence <= 1 for item in report.checks.findings)
    assert all(item.rule_id for item in report.checks.findings)
