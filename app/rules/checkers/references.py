"""Heuristic, offline citation and reference-list checks."""

from __future__ import annotations

import re

from rapidfuzz.fuzz import token_sort_ratio

from app.rules.checkers.common import body_elements, number_to_int, reference_elements, unique_in_order
from app.rules.findings import Finding
from app.rules.schemas import RuleDefinition
from app.schemas.document import DocumentElement, NormalizedDocument

_DIGITS = r"\d۰-۹٠-٩"
_NUMERIC_GROUP = re.compile(rf"\[\s*([{_DIGITS}\s,;،\-–—]+)\s*\]")
_NUMERIC_RANGE = re.compile(rf"\[\s*([{_DIGITS}]+)\s*\]\s*[-–—]\s*\[\s*([{_DIGITS}]+)\s*\]")
_AUTHOR_YEAR = re.compile(
    r"\(([A-Z][A-Za-z'’-]+(?:\s+et\s+al\.)?(?:\s*(?:&|and)\s*[A-Z][A-Za-z'’-]+)?"
    r"\s*,?\s*(?:19|20)\d{2}[a-z]?)\)",
    re.IGNORECASE,
)
_REFERENCE_PREFIX = re.compile(rf"^\s*\[\s*([{_DIGITS}]+)\s*\]\s*(.+)$")
_YEAR = re.compile(r"\b(?:18|19|20|21)\d{2}\b")
_DOI = re.compile(r"\b10\.\d{4,9}/\S+", re.IGNORECASE)


def expand_numeric_group(group: str) -> list[int]:
    """Expand [1,3-5] or [۱،۳–۵] content to ordered positive reference IDs."""
    values: list[int] = []
    for piece in re.split(r"[,;،]\s*", group.strip()):
        piece = piece.strip()
        if not piece:
            continue
        range_match = re.fullmatch(rf"([{_DIGITS}]+)\s*[-–—]\s*([{_DIGITS}]+)", piece)
        if range_match:
            start = number_to_int(range_match.group(1))
            end = number_to_int(range_match.group(2))
            if start is not None and end is not None and 0 < abs(end - start) <= 50:
                values.extend(range(min(start, end), max(start, end) + 1))
            elif start is not None:
                values.append(start)
            continue
        value = number_to_int(piece)
        if value is not None and value > 0:
            values.append(value)
    return values


def numeric_citations(elements: list[DocumentElement]) -> list[tuple[int, int, str]]:
    """Return (reference number, source index, original citation text) triples."""
    citations: list[tuple[int, int, str]] = []
    for element in elements:
        if element.metadata.get("is_caption"):
            continue
        text = element.text
        range_spans: list[tuple[int, int]] = []
        for match in _NUMERIC_RANGE.finditer(text):
            range_spans.append(match.span())
            start = number_to_int(match.group(1))
            end = number_to_int(match.group(2))
            if start is None or end is None:
                continue
            values = (
                list(range(min(start, end), max(start, end) + 1))
                if 0 < abs(end - start) <= 50
                else [start, end]
            )
            citations.extend((value, element.source_index, match.group(0)) for value in values)
        for match in _NUMERIC_GROUP.finditer(text):
            if any(start < match.end() and match.start() < end for start, end in range_spans):
                continue
            citations.extend(
                (value, element.source_index, match.group(0))
                for value in expand_numeric_group(match.group(1))
            )
    return citations


def _entries(
    elements: list[DocumentElement],
) -> tuple[list[tuple[int, DocumentElement, str]], list[DocumentElement]]:
    numbered: list[tuple[int, DocumentElement, str]] = []
    unnumbered: list[DocumentElement] = []
    for element in elements:
        text = element.text.strip()
        if not text:
            continue
        match = _REFERENCE_PREFIX.match(text)
        if match:
            value = number_to_int(match.group(1))
            if value is not None:
                numbered.append((value, element, match.group(2).strip()))
                continue
        if len(text) > 25 and (_YEAR.search(text) or _DOI.search(text) or "," in text):
            unnumbered.append(element)
    return numbered, unnumbered


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
        category="references",
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


def check_reference_parse_diagnostics(
    document: NormalizedDocument, rule: RuleDefinition
) -> list[Finding]:
    """Flag missing or incomplete bibliography structures without internet lookups."""
    reference_items = reference_elements(document)
    if not reference_items:
        return [
            _finding(
                rule, None,
                message_fa="بخش فهرست منابع تشخیص داده نشد؛ ممکن است عنوان آن متفاوت باشد.",
                message_en="A reference-list heading was not detected; the section may use another title.",
                fix_fa="عنوان بخش منابع را بررسی کنید و در صورت لزوم آن را به الگوهای مجاز اضافه کنید.",
                fix_en="Verify the reference-section heading and add accepted variants if needed.",
                severity="warning", confidence=0.82,
            )
        ]
    findings: list[Finding] = []
    numbered, unnumbered = _entries(reference_items)
    for number, element, raw in numbered:
        if not _YEAR.search(raw):
            findings.append(
                _finding(
                    rule, element,
                    message_fa=f"سال انتشار در مدخل شماره {number} به‌صورت قابل تشخیص پیدا نشد.",
                    message_en=f"No recognizable publication year was detected in reference entry {number}.",
                    fix_fa="سال را با منبع اصلی تطبیق دهید؛ اگر نامشخص است آن را جعل نکنید.",
                    fix_en="Check the original source for a year; do not invent one.",
                    snippet=element.text, severity="warning", confidence=0.7,
                )
            )
        if len(raw) < 20:
            findings.append(
                _finding(
                    rule, element,
                    message_fa=f"مدخل شماره {number} کوتاه است و شاید اطلاعات کتاب‌شناختی ناقص باشد.",
                    message_en=f"Reference entry {number} is unusually short and may have incomplete metadata.",
                    fix_fa="عنوان، نویسندگان و مشخصات انتشار را با منبع اصلی بررسی کنید.",
                    fix_en="Compare the title, authors, and publication details with the original source.",
                    snippet=element.text, severity="warning", confidence=0.65,
                )
            )
    for element in unnumbered:
        findings.append(
            _finding(
                rule, element,
                message_fa="مدخلی شبیه منبع پیدا شد که شماره IEEE آن تشخیص داده نشد.",
                message_en="A reference-like entry was found without a detectable IEEE-style number.",
                fix_fa="قالب این مدخل را دستی بررسی کنید؛ این تشخیص ابتکاری است.",
                fix_en="Review this entry manually; this is a heuristic detection.",
                snippet=element.text, severity="info", confidence=0.62,
            )
        )
    return findings


def check_reference_consistency(
    document: NormalizedDocument, rule: RuleDefinition
) -> list[Finding]:
    """Cross-check numeric citations, numbering, probable duplicates and style mixing."""
    body = body_elements(document)
    numbered_entries, _ = _entries(reference_elements(document))
    numeric = numeric_citations(body)
    author_year = [
        (element, match.group(0))
        for element in body for match in _AUTHOR_YEAR.finditer(element.text)
    ]
    findings: list[Finding] = []
    numeric_count, apa_count = len(numeric), len(author_year)
    style_total = numeric_count + apa_count
    if numeric_count and apa_count and style_total:
        ratio = min(numeric_count, apa_count) / style_total
        if ratio >= float(rule.parameters.get("mixed_style_min_ratio", 0.15)):
            element = author_year[0][0] if apa_count > numeric_count else next(
                (item for item in body if _NUMERIC_GROUP.search(item.text)), None
            )
            findings.append(
                _finding(
                    rule, element,
                    message_fa="نشانه‌های ارجاع عددی و نویسنده-سال هر دو در متن دیده شدند؛ سبک غالب قطعی نیست.",
                    message_en="Both numeric and author-year citation patterns appear in the body; the dominant style is uncertain.",
                    fix_fa="سبک مورد انتظار را با شیوه‌نامه بررسی کنید؛ همه موارد الزاماً خطا نیستند.",
                    fix_en="Confirm the required style; not every mixed-looking pattern is necessarily an error.",
                    snippet=element.text if element else "", severity="warning", confidence=0.72,
                )
            )

    listed_numbers = [value for value, _, _ in numbered_entries]
    listed_set = set(listed_numbers)
    cited_numbers = unique_in_order(number for number, _, _ in numeric)
    for missing in sorted(set(cited_numbers) - listed_set):
        citation = next((item for item in numeric if item[0] == missing), None)
        element = next((item for item in body if citation and item.source_index == citation[1]), None)
        findings.append(
            _finding(
                rule, element,
                message_fa=f"ارجاع عددی [{missing}] پیدا شد، اما مدخل شماره متناظر تشخیص داده نشد.",
                message_en=f"Numeric citation [{missing}] was found, but no matching numbered reference entry was detected.",
                fix_fa="شماره ارجاع را با فهرست منابع تطبیق دهید؛ منبع جایگزین نسازید.",
                fix_en="Reconcile the citation number with the list; do not fabricate a replacement source.",
                snippet=citation[2] if citation else "", severity="error", confidence=0.93,
            )
        )

    duplicate_numbers = sorted(number for number in set(listed_numbers) if listed_numbers.count(number) > 1)
    for number in duplicate_numbers:
        element = next(element for value, element, _ in numbered_entries if value == number)
        findings.append(
            _finding(
                rule, element,
                message_fa=f"شماره {number} بیش از یک بار در فهرست منابع استفاده شده است.",
                message_en=f"Reference number {number} appears more than once in the reference list.",
                fix_fa="شماره‌گذاری مدخل‌های فهرست را بازبینی کنید.",
                fix_en="Review numbering of reference-list entries.",
                snippet=element.text, severity="warning", confidence=0.96,
            )
        )

    if listed_numbers:
        for number in range(1, max(listed_numbers) + 1):
            if number not in listed_set:
                findings.append(
                    _finding(
                        rule, None,
                        message_fa=f"در شماره‌گذاری فهرست منابع، شماره {number} مفقود است.",
                        message_en=f"Reference numbering has a gap at {number}.",
                        fix_fa="شماره‌گذاری را پس از ویرایش بررسی کنید؛ حذف عمدی نیز ممکن است.",
                        fix_en="Review numbering after edits; a gap may be intentional.",
                        severity="warning", confidence=0.86,
                    )
                )
                break

    first_unique = unique_in_order(number for number, _, _ in numeric)
    if listed_numbers and numeric and not (set(cited_numbers) - listed_set):
        expected = list(range(1, len(first_unique) + 1))
        if first_unique != expected:
            element = next((item for item in body if _NUMERIC_GROUP.search(item.text)), None)
            findings.append(
                _finding(
                    rule, element,
                    message_fa="ترتیب اولین ظهور ارجاع‌های عددی با شماره‌گذاری پیوسته آغاز نمی‌شود.",
                    message_en="First-appearance order of numeric citations does not follow a continuous sequence.",
                    fix_fa="ترتیب شماره‌های ارجاع را طبق سبک مورد استفاده بازبینی کنید.",
                    fix_en="Review first-appearance citation ordering according to the chosen style.",
                    snippet=element.text if element else "", severity="warning", confidence=0.68,
                )
            )

    cited_set = set(cited_numbers)
    for number, element, _ in numbered_entries:
        if number not in cited_set:
            findings.append(
                _finding(
                    rule, element,
                    message_fa=f"مدخل منبع شماره {number} در الگوی ارجاع‌های شناسایی‌شده پیدا نشد.",
                    message_en=f"Reference entry {number} was not found in the detected in-text citation patterns.",
                    fix_fa="بررسی کنید منبع در متن استفاده شده است یا باید از فهرست حذف شود.",
                    fix_en="Check whether the source is cited in the body or should be removed.",
                    snippet=element.text, severity="warning", confidence=0.76,
                )
            )

    threshold = int(rule.parameters.get("fuzzy_duplicate_threshold", 92))
    for index, (number_a, _, raw_a) in enumerate(numbered_entries):
        for number_b, element_b, raw_b in numbered_entries[index + 1:]:
            if number_a == number_b:
                continue
            score = token_sort_ratio(raw_a, raw_b)
            if score >= threshold:
                findings.append(
                    _finding(
                        rule, element_b,
                        message_fa=f"مدخل‌های شماره {number_a} و {number_b} بسیار شبیه‌اند ({score}٪ شباهت متنی).",
                        message_en=f"Reference entries {number_a} and {number_b} are highly similar ({score}% text similarity).",
                        fix_fa="تکراری بودن را دستی با عنوان و شناسه منبع بررسی کنید؛ شباهت متنی اثبات تکرار نیست.",
                        fix_en="Verify duplication using titles/source IDs; text similarity alone is not proof.",
                        snippet=element_b.text, severity="warning", confidence=min(0.92, score / 100),
                    )
                )
    return findings
