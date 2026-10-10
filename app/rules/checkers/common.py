"""Shared utilities for document checkers."""

import re
from collections.abc import Iterable

from app.parsing.normalization import normalize_for_comparison
from app.schemas.document import DocumentElement, NormalizedDocument


def is_reference_heading(text: str) -> bool:
    normalized = normalize_for_comparison(text).casefold()
    return any(
        term in normalized
        for term in ("references", "bibliography", "منابع", "مراجع", "کتابنامه")
    )


def reference_section_start(document: NormalizedDocument) -> int | None:
    for index, element in enumerate(document.elements):
        if element.kind == "heading" and is_reference_heading(element.text):
            return index
    return None


def body_elements(document: NormalizedDocument) -> list[DocumentElement]:
    start = reference_section_start(document)
    return document.elements[:start] if start is not None else document.elements


def reference_elements(document: NormalizedDocument) -> list[DocumentElement]:
    start = reference_section_start(document)
    if start is None:
        return []
    result: list[DocumentElement] = []
    for element in document.elements[start + 1 :]:
        if element.kind == "heading" and element.heading_level == 1:
            break
        if element.text.strip():
            result.append(element)
    return result


def number_to_int(value: str) -> int | None:
    translated = value.translate(
        str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    )
    return int(translated) if translated.isdigit() else None


def normalized_key(text: str) -> str:
    value = normalize_for_comparison(text).casefold()
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def unique_in_order(values: Iterable[int]) -> list[int]:
    return list(dict.fromkeys(values))
