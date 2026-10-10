"""Registry-based rule runner for deterministic, evidence-bearing findings."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from app.rules.checkers.abstracts import check_abstract_consistency, check_abstract_presence
from app.rules.checkers.figures_tables import check_figure_table_consistency
from app.rules.checkers.formatting import (
    check_docx_body_font,
    check_docx_line_spacing,
    check_docx_page_margins,
)
from app.rules.checkers.references import (
    check_reference_consistency,
    check_reference_parse_diagnostics,
)
from app.rules.checkers.structure import check_heading_hierarchy, check_required_sections
from app.rules.checkers.terminology import check_terminology_consistency
from app.rules.findings import CheckReport, Finding, RuleResult
from app.rules.schemas import RuleDefinition, RuleSet
from app.schemas.document import NormalizedDocument

Checker = Callable[[NormalizedDocument, RuleDefinition], list[Finding]]
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _terminology_adapter(document: NormalizedDocument, rule: RuleDefinition) -> list[Finding]:
    path = rule.parameters.get("glossary_path", "glossary/terms_seed.csv")
    glossary = Path(str(path))
    if not glossary.is_absolute():
        glossary = _PROJECT_ROOT / glossary
    return check_terminology_consistency(document, rule, glossary_path=glossary)


CHECKER_REGISTRY: dict[str, Checker] = {
    "abstract_presence": check_abstract_presence,
    "abstract_consistency": check_abstract_consistency,
    "figure_table_consistency": check_figure_table_consistency,
    "docx_body_font": check_docx_body_font,
    "docx_page_margins": check_docx_page_margins,
    "docx_line_spacing": check_docx_line_spacing,
    "reference_consistency": check_reference_consistency,
    "reference_parse_diagnostics": check_reference_parse_diagnostics,
    "required_sections": check_required_sections,
    "heading_hierarchy": check_heading_hierarchy,
    "terminology_consistency": _terminology_adapter,
}


def _skip_reason(
    document: NormalizedDocument, rule: RuleDefinition
) -> tuple[bool, str, str]:
    """Skip checks that cannot run or have no verified configuration."""
    if not rule.enabled:
        return True, "این قاعده در مجموعه قوانین غیرفعال است.", "This rule is disabled in the ruleset."
    if rule.checker not in CHECKER_REGISTRY:
        return True, "پیاده‌سازی این نوع بررسی موجود نیست.", "This checker is not implemented."
    if rule.checker in {"docx_body_font", "docx_page_margins", "docx_line_spacing"}:
        if document.source_format != "docx":
            return True, "این بررسی فقط برای DOCX پشتیبانی می‌شود.", "This check is supported for DOCX only."
        if rule.checker == "docx_body_font":
            expected = [
                str(rule.parameters.get("expected_persian_font") or ""),
                str(rule.parameters.get("expected_latin_font") or ""),
            ]
            if not all(value and not value.startswith("REPLACE_") for value in expected):
                return True, "قلم رسمی در مجموعه قوانین تنظیم نشده است.", "Expected fonts are not configured."
        elif rule.checker == "docx_page_margins":
            if not any(rule.parameters.get(key) is not None for key in (
                "top_cm", "bottom_cm", "left_cm", "right_cm"
            )):
                return True, "حاشیه‌های رسمی در مجموعه قوانین تنظیم نشده‌اند.", "Margins are not configured."
        elif rule.parameters.get("expected_multiple") is None:
            return True, "فاصله خطوط رسمی در مجموعه قوانین تنظیم نشده است.", "Line spacing is not configured."
    if rule.checker == "required_sections" and not str(rule.parameters.get("required_headings", "")).strip():
        return True, "عنوان‌های الزامی از شیوه‌نامه رسمی تنظیم نشده‌اند.", "Required headings are not configured."
    return False, "", ""


def run_rules(
    document: NormalizedDocument,
    ruleset: RuleSet,
    *,
    max_findings: int = 500,
) -> CheckReport:
    """Run enabled, configured deterministic checks; isolate checker failures."""
    findings: list[Finding] = []
    results: list[RuleResult] = []
    checked = 0
    skipped = 0
    for rule in ruleset.rules:
        should_skip, note_fa, note_en = _skip_reason(document, rule)
        if should_skip:
            skipped += 1
            results.append(
                RuleResult(
                    rule_id=rule.id,
                    title_fa=rule.title.fa,
                    title_en=rule.title.en,
                    severity=rule.severity,
                    status="skipped",
                    note_fa=note_fa,
                    note_en=note_en,
                )
            )
            continue
        checked += 1
        try:
            rule_findings = CHECKER_REGISTRY[rule.checker](document, rule)
            findings.extend(rule_findings)
            results.append(
                RuleResult(
                    rule_id=rule.id,
                    title_fa=rule.title.fa,
                    title_en=rule.title.en,
                    severity=rule.severity,
                    status="issues_found" if rule_findings else "passed",
                    findings_count=len(rule_findings),
                    note_fa=(
                        f"{len(rule_findings)} مورد برای بازبینی شناسایی شد."
                        if rule_findings else "موردی توسط این قاعده شناسایی نشد."
                    ),
                    note_en=(
                        f"{len(rule_findings)} item(s) flagged for review."
                        if rule_findings else "No item was flagged by this rule."
                    ),
                )
            )
        except Exception:
            # Avoid returning document data or raw exception details to the caller.
            skipped += 1
            results.append(
                RuleResult(
                    rule_id=rule.id,
                    title_fa=rule.title.fa,
                    title_en=rule.title.en,
                    severity=rule.severity,
                    status="skipped",
                    note_fa="اجرای این قاعده به مشکل خورد؛ متن سند در پیام خطا ثبت نشده است.",
                    note_en="The checker failed safely; document text is not included in the error.",
                )
            )
    severity_order = {"error": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda item: (severity_order[item.severity], -item.confidence, item.rule_id))
    return CheckReport(
        ruleset_name=ruleset.metadata.name,
        ruleset_version=ruleset.metadata.version,
        ruleset_verified=(
            ruleset.metadata.status == "verified"
            and ruleset.metadata.official_guideline_verified
        ),
        disclaimer_fa=ruleset.metadata.warning.fa,
        disclaimer_en=ruleset.metadata.warning.en,
        rules_checked=checked,
        rules_skipped=skipped,
        findings=findings[:max_findings],
        results=results,
    )
