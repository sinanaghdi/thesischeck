"""Deterministic checks for abstract presence and bilingual structure."""

from __future__ import annotations

import re
from collections import Counter

from app.parsing.normalization import normalize_for_comparison
from app.rules.checkers.common import body_elements
from app.rules.findings import Finding
from app.rules.schemas import RuleDefinition
from app.schemas.document import DocumentElement, NormalizedDocument

_FA_ABSTRACT = ("چکیده", "چكيده", "خلاصه")
_EN_ABSTRACT = ("abstract",)
_KEYWORDS_RE = re.compile(
    r"(?:واژگان\s*کلیدی|کلمات\s*کلیدی|کلیدواژه(?:ها)?|keywords?)\s*[:：\-]\s*(.+)",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"(?<![A-Za-z])\d+(?:[.,]\d+)?%?")
_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _is_heading(text: str) -> bool:
    return text.strip().casefold() in {term.casefold() for term in (*_FA_ABSTRACT, *_EN_ABSTRACT)}


def _abstract_blocks(
    document: NormalizedDocument, terms: tuple[str, ...]
) -> tuple[DocumentElement | None, list[DocumentElement]]:
    elements = body_elements(document)
    target_index = None
    target = None
    lowered_terms = {term.casefold() for term in terms}
    for index, element in enumerate(elements):
        normalized = normalize_for_comparison(element.text).strip().casefold()
        if element.kind == "heading" and (
            normalized in lowered_terms
            or any(normalized.startswith(term.casefold() + " ") for term in terms)
        ):
            target_index, target = index, element
            break
    if target_index is None:
        # Some Word files use a styled first paragraph rather than an explicit heading.
        for index, element in enumerate(elements):
            if any(normalize_for_comparison(element.text).strip().casefold().startswith(term) for term in lowered_terms):
                target_index, target = index, element
                break
    if target_index is None:
        return None, []
    level = target.heading_level or 1
    block: list[DocumentElement] = []
    for element in elements[target_index + 1 :]:
        if element.kind == "heading" and (element.heading_level or 1) <= level:
            break
        block.append(element)
    return target, block


def _keyword_list(block: list[DocumentElement]) -> tuple[DocumentElement | None, list[str]]:
    for element in block:
        match = _KEYWORDS_RE.search(element.text)
        if match:
            keywords = [
                item.strip(" \t.;،؛")
                for item in re.split(r"[،,;؛]", match.group(1))
                if item.strip(" \t.;،؛")
            ]
            return element, keywords
    return None, []


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
        category="abstracts",
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


def check_abstract_presence(
    document: NormalizedDocument, rule: RuleDefinition
) -> list[Finding]:
    """Check for recognizable Persian and English abstract sections."""
    fa_heading, _ = _abstract_blocks(document, _FA_ABSTRACT)
    en_heading, _ = _abstract_blocks(document, _EN_ABSTRACT)
    findings: list[Finding] = []
    if fa_heading is None:
        findings.append(
            _finding(
                rule, None,
                message_fa="عنوان چکیده فارسی شناسایی نشد.",
                message_en="A Persian abstract heading was not detected.",
                fix_fa="وجود چکیده فارسی و عنوان آن را در سند بررسی کنید؛ ممکن است تشخیص عنوان نیازمند تنظیم باشد.",
                fix_en="Verify the Persian abstract and its heading; the heading detector may need adjustment.",
                confidence=0.82,
            )
        )
    if en_heading is None:
        findings.append(
            _finding(
                rule, None,
                message_fa="عنوان چکیده انگلیسی شناسایی نشد.",
                message_en="An English abstract heading was not detected.",
                fix_fa="وجود چکیده انگلیسی و عنوان آن را در سند بررسی کنید.",
                fix_en="Verify that an English abstract and its heading are present.",
                confidence=0.88,
            )
        )
    return findings


def check_abstract_consistency(
    document: NormalizedDocument, rule: RuleDefinition
) -> list[Finding]:
    """Compare keyword counts, approximate length, and explicit numeric tokens offline."""
    fa_heading, fa_block = _abstract_blocks(document, _FA_ABSTRACT)
    en_heading, en_block = _abstract_blocks(document, _EN_ABSTRACT)
    if fa_heading is None or en_heading is None:
        # Missing-section findings are owned by abstract_presence; avoid duplicate claims.
        return []
    fa_text = "\n".join(element.text for element in fa_block)
    en_text = "\n".join(element.text for element in en_block)
    findings: list[Finding] = []
    fa_keyword_element, fa_keywords = _keyword_list(fa_block)
    en_keyword_element, en_keywords = _keyword_list(en_block)
    if (fa_keyword_element is None) != (en_keyword_element is None):
        element = fa_keyword_element or en_keyword_element or fa_heading
        findings.append(
            _finding(
                rule, element,
                message_fa="فهرست واژگان کلیدی فقط در یکی از دو چکیده شناسایی شد.",
                message_en="A keyword list was detected in only one of the two abstracts.",
                fix_fa="وجود فهرست واژگان کلیدی در هر دو زبان را بررسی کنید.",
                fix_en="Check whether keyword lists are present in both language versions.",
                snippet=element.text,
                confidence=0.86,
            )
        )
    elif fa_keyword_element is not None and en_keyword_element is not None and len(fa_keywords) != len(en_keywords):
        findings.append(
            _finding(
                rule, en_keyword_element,
                message_fa=f"تعداد واژگان کلیدی یکسان نیست: فارسی {len(fa_keywords)} مورد و انگلیسی {len(en_keywords)} مورد.",
                message_en=f"Keyword counts differ: {len(fa_keywords)} in Persian and {len(en_keywords)} in English.",
                fix_fa="فهرست‌ها را از نظر تعداد و تطابق معنایی دستی مقایسه کنید.",
                fix_en="Compare both keyword lists manually for count and semantic equivalence.",
                snippet=en_keyword_element.text,
                confidence=0.98,
            )
        )

    fa_words = len(re.findall(r"[\w\u0600-\u06ff]+", fa_text, flags=re.UNICODE))
    en_words = len(re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*", en_text))
    if min(fa_words, en_words) >= 20:
        ratio = min(fa_words, en_words) / max(fa_words, en_words)
        threshold = float(rule.parameters.get("minimum_length_ratio", 0.45))
        if ratio < threshold:
            findings.append(
                _finding(
                    rule, en_heading,
                    message_fa=f"اختلاف قابل‌توجهی در طول دو چکیده دیده شد (نسبت طول تقریبی {ratio:.2f}).",
                    message_en=f"The abstract lengths differ substantially (approximate length ratio {ratio:.2f}).",
                    fix_fa="اختلاف طول به‌تنهایی خطا نیست؛ بررسی کنید مسئله، روش، نتایج و نتیجه‌گیری در هر دو نسخه پوشش داده شوند.",
                    fix_en="Length difference alone is not an error; verify that problem, method, results, and conclusion are covered in both versions.",
                    snippet=en_text[:300],
                    severity="warning",
                    confidence=0.7,
                )
            )

    fa_numbers = Counter(match.group(0).translate(_PERSIAN_DIGITS) for match in _NUMBER_RE.finditer(fa_text))
    en_numbers = Counter(match.group(0).translate(_PERSIAN_DIGITS) for match in _NUMBER_RE.finditer(en_text))
    differing = sorted((fa_numbers - en_numbers).keys())[:5] + sorted((en_numbers - fa_numbers).keys())[:5]
    if differing and fa_numbers and en_numbers:
        findings.append(
            _finding(
                rule, en_heading,
                message_fa="مقادیر عددی یکسانی در دو چکیده تشخیص داده نشد؛ اختلاف باید دستی بررسی شود.",
                message_en="Some numeric tokens differ between abstracts; the discrepancy needs manual review.",
                fix_fa="عددها و معیارها را با متن اصلی تطبیق دهید؛ سیستم معنای عددها را استنتاج نمی‌کند.",
                fix_en="Compare values and metrics against the source; the checker does not infer their meaning.",
                snippet=f"Persian: {', '.join(fa_numbers.keys())}; English: {', '.join(en_numbers.keys())}",
                severity="warning",
                confidence=0.65,
            )
        )
    return findings
