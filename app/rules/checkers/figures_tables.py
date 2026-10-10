"""Deterministic caption sequence and in-text cross-reference checks."""

from __future__ import annotations

import re
from collections import defaultdict

from app.parsing.normalization import normalize_for_comparison
from app.rules.checkers.common import body_elements, number_to_int
from app.rules.findings import Finding
from app.rules.schemas import RuleDefinition
from app.schemas.document import DocumentElement, NormalizedDocument

_CAPTION_RE = re.compile(
    r"^\s*(شکل|تصویر|جدول|الگوریتم|figure|fig\.?|table|algorithm)\s*[-:]?\s*"
    r"([\d۰-۹٠-٩]+(?:[-.][\d۰-۹٠-٩]+)*)",
    re.IGNORECASE,
)
_REF_RE = re.compile(
    r"(?:شکل|تصویر|جدول|الگوریتم|figure|fig\.?|table|algorithm)\s*"
    r"([\d۰-۹٠-٩]+(?:[-.][\d۰-۹٠-٩]+)*)",
    re.IGNORECASE,
)


def _english_label(label: str) -> str:
    return {
        "شکل": "figure",
        "تصویر": "figure",
        "جدول": "table",
        "الگوریتم": "algorithm",
        "fig.": "figure",
        "fig": "figure",
    }.get(label.casefold(), label)

def _key(label: str, number: str) -> tuple[str, tuple[int, ...]]:
    parts = tuple(
        number_to_int(part) or 0 for part in re.split(r"[-.]", number)
    )
    normalized_label = label.casefold()
    if normalized_label in {"fig.", "fig"}:
        normalized_label = "figure"
    if normalized_label in {"تصویر"}:
        normalized_label = "شکل"
    return normalized_label, parts


def _finding(
    rule: RuleDefinition,
    element: DocumentElement | None,
    *,
    message_fa: str,
    message_en: str,
    fix_fa: str,
    fix_en: str,
    snippet: str = "",
    severity: str | None = None,
    confidence: float = 0.9,
) -> Finding:
    return Finding(
        rule_id=rule.id,
        category="figures_tables",
        severity=severity or rule.severity,
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


def check_figure_table_consistency(
    document: NormalizedDocument, rule: RuleDefinition
) -> list[Finding]:
    """Identify duplicate captions, missing caption references, and dangling body references."""
    captions: dict[tuple[str, tuple[int, ...]], list[DocumentElement]] = defaultdict(list)
    body_refs: dict[tuple[str, tuple[int, ...]], list[DocumentElement]] = defaultdict(list)
    all_elements = document.elements
    for element in all_elements:
        text = normalize_for_comparison(element.text)
        caption = _CAPTION_RE.match(text)
        if caption:
            captions[_key(caption.group(1), caption.group(2))].append(element)

    for element in body_elements(document):
        if element.metadata.get("is_caption"):
            continue
        for match in _REF_RE.finditer(normalize_for_comparison(element.text)):
            # Avoid counting the label at the beginning of an actual caption.
            if _CAPTION_RE.match(normalize_for_comparison(element.text)):
                continue
            body_refs[_key(match.group(0).split()[0], match.group(1))].append(element)

    findings: list[Finding] = []
    for caption_key, elements in captions.items():
        label, parts = caption_key
        if len(elements) > 1:
            for duplicate in elements[1:]:
                findings.append(
                    _finding(
                        rule, duplicate,
                        message_fa=f"شماره کپشن «{label} {'-'.join(map(str, parts))}» بیش از یک بار دیده شد.",
                        message_en=f"Caption number “{_english_label(label)} {'-'.join(map(str, parts))}” appears more than once.",
                        fix_fa="شماره و ارجاع‌های مرتبط را در سند اصلی بررسی کنید.",
                        fix_en="Review the caption number and related cross-references in the original document.",
                        snippet=duplicate.text,
                        severity="warning",
                        confidence=0.96,
                    )
                )
        if caption_key not in body_refs:
            findings.append(
                _finding(
                    rule, elements[0],
                    message_fa=f"برای کپشن «{label} {'-'.join(map(str, parts))}» ارجاعی در متن شناسایی نشد.",
                    message_en=f"No in-text reference was detected for caption “{_english_label(label)} {'-'.join(map(str, parts))}”.",
                    fix_fa="بررسی کنید که شکل یا جدول در متن معرفی شده باشد؛ ممکن است الگوی ارجاع متفاوت باشد.",
                    fix_en="Check that the figure or table is referenced in the body; the reference phrasing may differ.",
                    snippet=elements[0].text,
                    severity="warning",
                    confidence=0.82,
                )
            )

    for ref_key, elements in body_refs.items():
        if ref_key not in captions:
            label, parts = ref_key
            element = elements[0]
            findings.append(
                _finding(
                    rule, element,
                    message_fa=f"ارجاعی به «{label} {'-'.join(map(str, parts))}» دیده شد، اما کپشن متناظر تشخیص داده نشد.",
                    message_en=f"A reference to “{_english_label(label)} {'-'.join(map(str, parts))}” was found, but no matching caption was detected.",
                    fix_fa="وجود کپشن و شماره آن را بررسی کنید؛ استخراج تصویرهای PDF ممکن است ناقص باشد.",
                    fix_en="Check that the caption and number exist; PDF image/caption extraction may be incomplete.",
                    snippet=element.text,
                    severity="warning",
                    confidence=0.78,
                )
            )

    # Numbering continuity is checked only for simple sequential numbering under the same label.
    grouped: dict[str, list[tuple[int, DocumentElement]]] = defaultdict(list)
    for (label, parts), elements in captions.items():
        if len(parts) == 1 and parts[0] > 0:
            grouped[label].append((parts[0], elements[0]))
    for label, entries in grouped.items():
        numbers = sorted({number for number, _ in entries})
        if numbers and numbers[0] == 1 and numbers != list(range(1, max(numbers) + 1)):
            missing = next(number for number in range(1, max(numbers) + 1) if number not in numbers)
            element = next(element for number, element in entries if number > missing)
            findings.append(
                _finding(
                    rule, element,
                    message_fa=f"در توالی شماره‌گذاری «{label}»، شماره {missing} شناسایی نشد.",
                    message_en=f"Caption numbering for “{_english_label(label)}” has a gap at {missing}.",
                    fix_fa="شماره‌ها را طبق سبک شماره‌گذاری سند بررسی کنید؛ در شماره‌گذاری فصل‌محور این هشدار ممکن است کاربرد نداشته باشد.",
                    fix_en="Review numbering against the document style; chapter-based numbering may make this warning inapplicable.",
                    snippet=element.text,
                    severity="info",
                    confidence=0.68,
                )
            )
    return findings
