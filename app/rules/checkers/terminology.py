"""Offline terminology consistency checks backed by an editable CSV glossary."""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

from app.parsing.normalization import normalize_for_comparison
from app.rules.checkers.common import body_elements, normalized_key
from app.rules.findings import Finding
from app.rules.schemas import RuleDefinition
from app.schemas.document import DocumentElement, NormalizedDocument

_PERSIAN_ENGLISH_PAIR = re.compile(
    r"(?P<persian>[\u0600-\u06ff‌][\u0600-\u06ff\s‌]{1,60})\s*[\(（]"
    r"\s*(?P<english>[A-Za-z][A-Za-z0-9 +./-]{1,80})\s*[\)）]"
)


def load_glossary(path: str | Path) -> list[dict[str, str | list[str]]]:
    """Load an editable glossary CSV; malformed rows are rejected, blank rows ignored."""
    rows: list[dict[str, str | list[str]]] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"english_term", "canonical_fa", "accepted_variants"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError("Glossary CSV must define english_term, canonical_fa, accepted_variants")
        for row in reader:
            english = (row.get("english_term") or "").strip()
            canonical = normalize_for_comparison(row.get("canonical_fa") or "").strip()
            variants = [
                normalize_for_comparison(part).strip()
                for part in (row.get("accepted_variants") or "").split("|")
                if part.strip()
            ]
            if english and canonical:
                rows.append(
                    {
                        "english_term": english,
                        "canonical_fa": canonical,
                        "accepted_variants": variants,
                    }
                )
    return rows


def _make_finding(
    rule: RuleDefinition,
    element: DocumentElement,
    *,
    english_term: str,
    variants: list[str],
    canonical: str,
    counts: Counter[str],
) -> Finding:
    most_frequent = max(variants, key=lambda item: counts[item])
    return Finding(
        rule_id=rule.id,
        category="terminology",
        severity=rule.severity,
        title_fa=rule.title.fa,
        title_en=rule.title.en,
        message_fa=(
            f"برای اصطلاح «{english_term}»، چند صورت فارسی مشاهده شد: "
            f"{'، '.join(variants)}. صورت پرتکرار: «{most_frequent}»."
        ),
        message_en=(
            f"Multiple Persian variants were observed for “{english_term}”: "
            f"{', '.join(variants)}. Most frequent: “{most_frequent}”."
        ),
        element_id=element.element_id,
        heading_path=element.heading_path,
        page_number=element.page_number,
        snippet=element.text[:300],
        suggested_fix_fa=(
            f"معادل پیشنهادی «{canonical}» را بررسی کنید؛ معنای علمی و بافت جمله را دستی تأیید کنید."
        ),
        suggested_fix_en=(
            f"Consider “{canonical}” as the preferred equivalent, then confirm the scientific meaning "
            "and context manually."
        ),
        confidence=0.78,
    )


def check_terminology_consistency(
    document: NormalizedDocument,
    rule: RuleDefinition,
    *,
    glossary_path: str | Path,
) -> list[Finding]:
    """Flag multiple glossary variants and repeated English terms with local Persian equivalents."""
    glossary = load_glossary(glossary_path)
    elements = body_elements(document)
    findings: list[Finding] = []
    reported: set[tuple[str, tuple[str, ...]]] = set()

    for term in glossary:
        english = str(term["english_term"])
        canonical = str(term["canonical_fa"])
        variants = [str(item) for item in term["accepted_variants"]]
        forms = list(dict.fromkeys([canonical, *variants]))
        counts: Counter[str] = Counter()
        first: DocumentElement | None = None
        for element in elements:
            text = normalize_for_comparison(element.text)
            for variant in forms:
                count = len(re.findall(re.escape(variant), text, flags=re.IGNORECASE))
                if count:
                    counts[variant] += count
                    first = first or element
        observed = [variant for variant in forms if counts[variant] > 0]
        if len(observed) > 1 and first is not None:
            key = (english.casefold(), tuple(sorted(normalized_key(item) for item in observed)))
            reported.add(key)
            findings.append(
                _make_finding(
                    rule, first, english_term=english, variants=observed,
                    canonical=canonical, counts=counts,
                )
            )

    # A cautious supplement for local terms not yet included in the seed glossary.
    translations: dict[str, dict[str, list[DocumentElement]]] = defaultdict(lambda: defaultdict(list))
    for element in elements:
        for match in _PERSIAN_ENGLISH_PAIR.finditer(normalize_for_comparison(element.text)):
            persian = match.group("persian").strip(" ،؛:.-")
            english = match.group("english").strip()
            if not persian or len(persian.split()) > 4:
                continue
            translations[english.casefold()][persian].append(element)
    for english, variant_map in translations.items():
        if len(variant_map) < 2:
            continue
        variants = list(variant_map)
        key = (english, tuple(sorted(normalized_key(item) for item in variants)))
        if key in reported:
            continue
        counts = Counter({variant: len(items) for variant, items in variant_map.items()})
        first = next(iter(next(iter(variant_map.values()))))
        findings.append(
            _make_finding(
                rule, first, english_term=english, variants=variants,
                canonical=max(counts, key=counts.get), counts=counts,
            )
        )
    return findings
