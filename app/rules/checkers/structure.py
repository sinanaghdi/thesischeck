"""Basic structural consistency checks independent of university-specific requirements."""

from __future__ import annotations

from app.rules.findings import Finding
from app.rules.schemas import RuleDefinition
from app.schemas.document import NormalizedDocument


def check_required_sections(
    document: NormalizedDocument, rule: RuleDefinition
) -> list[Finding]:
    """Check headings supplied by an explicitly configured ruleset parameter."""
    raw = str(rule.parameters.get("required_headings", "")).strip()
    required = [part.strip() for part in raw.split("|") if part.strip()]
    if not required:
        return []
    detected = [element.text.casefold().strip() for element in document.elements if element.kind == "heading"]
    missing = [heading for heading in required if not any(heading.casefold() in item for item in detected)]
    return [
        Finding(
            rule_id=rule.id,
            category="structure",
            severity=rule.severity,
            title_fa=rule.title.fa,
            title_en=rule.title.en,
            message_fa=f"عنوان الزامی پیکربندی‌شده شناسایی نشد: «{heading}».",
            message_en=f"Configured required heading was not detected: “{heading}”.",
            snippet="",
            suggested_fix_fa="عنوان‌های الزامی را فقط بر اساس شیوه‌نامه رسمی دانشکده وارد کنید.",
            suggested_fix_en="Configure required headings only after checking the official faculty guideline.",
            confidence=0.8,
        )
        for heading in missing
    ]


def check_heading_hierarchy(
    document: NormalizedDocument, rule: RuleDefinition
) -> list[Finding]:
    """Flag jumps in detected heading levels as a review hint, not an official violation."""
    findings: list[Finding] = []
    previous_level: int | None = None
    for element in document.elements:
        if element.kind != "heading" or element.heading_level is None:
            continue
        level = element.heading_level
        if previous_level is not None and level > previous_level + 1:
            findings.append(
                Finding(
                    rule_id=rule.id,
                    category="structure",
                    severity=rule.severity,
                    title_fa=rule.title.fa,
                    title_en=rule.title.en,
                    message_fa=f"سطح عنوان از {previous_level} به {level} جهش دارد؛ ممکن است سطح میانی وجود نداشته باشد.",
                    message_en=f"Heading level jumps from {previous_level} to {level}; an intermediate level may be missing.",
                    element_id=element.element_id,
                    heading_path=element.heading_path,
                    page_number=element.page_number,
                    snippet=element.text[:300],
                    suggested_fix_fa="سطح و سبک عنوان‌ها را در Word بررسی کنید؛ این هشدار به‌تنهایی اثبات خطا نیست.",
                    suggested_fix_en="Review heading levels and styles in Word; this hint alone does not prove an error.",
                    confidence=0.7,
                )
            )
        previous_level = level
    return findings
