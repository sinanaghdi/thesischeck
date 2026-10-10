"""Rule-driven DOCX formatting checkers; no defaults are presented as official requirements."""

from __future__ import annotations

from typing import Any

from app.rules.findings import Finding
from app.rules.schemas import RuleDefinition
from app.schemas.document import DocumentElement, NormalizedDocument


def _finding(
    rule: RuleDefinition,
    element: DocumentElement | None,
    *,
    message_fa: str,
    message_en: str,
    fix_fa: str,
    fix_en: str,
    snippet: str = "",
    confidence: float = 0.9,
) -> Finding:
    return Finding(
        rule_id=rule.id,
        category="formatting",
        severity=rule.severity,
        title_fa=rule.title.fa,
        title_en=rule.title.en,
        message_fa=message_fa,
        message_en=message_en,
        element_id=element.element_id if element else None,
        heading_path=element.heading_path if element else [],
        page_number=element.page_number if element else None,
        snippet=snippet[:300],
        suggested_fix_fa=fix_fa,
        suggested_fix_en=fix_en,
        confidence=confidence,
    )


def _same_font(actual: str | None, expected: str) -> bool:
    return bool(actual) and actual.strip().casefold() == expected.strip().casefold()


def check_docx_body_font(
    document: NormalizedDocument, rule: RuleDefinition
) -> list[Finding]:
    """Compare run font metadata against explicit, non-placeholder expectations."""
    expected_persian = str(rule.parameters.get("expected_persian_font") or "").strip()
    expected_latin = str(rule.parameters.get("expected_latin_font") or "").strip()
    findings: list[Finding] = []
    for element in document.elements:
        if element.kind not in {"paragraph", "heading"}:
            continue
        runs = element.metadata.get("runs", [])
        for run in runs if isinstance(runs, list) else []:
            if not isinstance(run, dict):
                continue
            text = str(run.get("text") or "")
            actual = (
                run.get("font_complex_script")
                or run.get("font_ascii")
                or run.get("font_hansi")
                or run.get("font_name")
            )
            if any("\u0600" <= char <= "\u06ff" for char in text):
                expected = expected_persian
                language = "فارسی"
            elif any(char.isascii() and char.isalpha() for char in text):
                expected = expected_latin
                language = "لاتین"
            else:
                continue
            if expected and not _same_font(str(actual) if actual else None, expected):
                findings.append(
                    _finding(
                        rule, element,
                        message_fa=f"قلم {language} این بخش با قلم پیکربندی‌شده یکسان تشخیص داده نشد.",
                        message_en="The font for this run does not match the configured expectation.",
                        fix_fa="قلم را فقط پس از تأیید مقدار رسمی شیوه‌نامه تنظیم کنید؛ قالب‌بندی مستقیم و سبک ارث‌رسیده ممکن است متفاوت باشد.",
                        fix_en="Set the font only after verifying the official requirement; direct formatting and inherited styles may differ.",
                        snippet=text,
                        confidence=0.72 if not actual else 0.88,
                    )
                )
    return findings


def check_docx_page_margins(
    document: NormalizedDocument, rule: RuleDefinition
) -> list[Finding]:
    """Compare known section margins to configured centimeter values."""
    expected_map = {
        "top_cm": "top_margin_cm",
        "bottom_cm": "bottom_margin_cm",
        "left_cm": "left_margin_cm",
        "right_cm": "right_margin_cm",
    }
    configured = {
        param: float(rule.parameters[param])
        for param in expected_map
        if rule.parameters.get(param) is not None
    }
    if not configured:
        return []
    findings: list[Finding] = []
    for section in document.format_metadata.get("sections", []):
        if not isinstance(section, dict):
            continue
        for param, metadata_key in expected_map.items():
            if param not in configured:
                continue
            actual = section.get(metadata_key)
            if actual is None:
                continue
            expected = configured[param]
            if abs(float(actual) - expected) > float(rule.parameters.get("tolerance_cm", 0.05)):
                findings.append(
                    _finding(
                        rule, None,
                        message_fa=f"حاشیه {metadata_key.replace('_cm', '')} در بخش {section.get('section')} با مقدار پیکربندی‌شده تفاوت دارد.",
                        message_en=f"Section {section.get('section')} has a margin that differs from the configured value.",
                        fix_fa="مقدار مورد انتظار باید از شیوه‌نامه رسمی تأیید شده باشد؛ تنظیمات بخش را در Word بررسی کنید.",
                        fix_en="The expected value must be verified against the official guideline; inspect Word section setup.",
                        snippet=f"actual={actual} cm; expected={expected} cm",
                        confidence=0.88,
                    )
                )
    return findings


def check_docx_line_spacing(
    document: NormalizedDocument, rule: RuleDefinition
) -> list[Finding]:
    """Check numeric paragraph spacing where DOCX exposes a comparable multiple."""
    expected = rule.parameters.get("expected_multiple")
    if expected is None:
        return []
    expected_value = float(expected)
    findings: list[Finding] = []
    for element in document.elements:
        if element.kind not in {"paragraph", "heading"}:
            continue
        actual: Any = element.metadata.get("line_spacing")
        try:
            actual_value = float(actual)
        except (TypeError, ValueError):
            continue
        if abs(actual_value - expected_value) > float(rule.parameters.get("tolerance", 0.03)):
            findings.append(
                _finding(
                    rule, element,
                    message_fa="فاصله خطوط این پاراگراف با مقدار پیکربندی‌شده تفاوت دارد.",
                    message_en="This paragraph's line spacing differs from the configured value.",
                    fix_fa="مقدار رسمی فاصله خطوط را تأیید کنید؛ مقادیر مبتنی بر نقطه ممکن است با ضریب فاصله یکسان نباشند.",
                    fix_en="Verify the official line spacing; point-based spacing values are not equivalent to a line-spacing multiple.",
                    snippet=element.text,
                    confidence=0.72,
                )
            )
    return findings
