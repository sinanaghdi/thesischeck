"""Conservative Persian/Arabic normalization for comparisons.

Source text must be retained separately; these functions never rewrite the original.
"""

import re
import unicodedata

_ARABIC_TO_PERSIAN = str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک"})
_PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_LATIN_DIGITS = "0123456789"
_DIGIT_TRANSLATION = str.maketrans(
    {**dict(zip(_PERSIAN_DIGITS, _LATIN_DIGITS)), **dict(zip(_ARABIC_DIGITS, _LATIN_DIGITS))}
)
_WHITESPACE = re.compile(r"[\t\r\n ]+")


def normalize_persian_text(text: str, *, latin_digits: bool = True) -> str:
    """Normalize Unicode, Arabic yeh/kaf and optionally digits for comparison."""
    value = unicodedata.normalize("NFC", text).translate(_ARABIC_TO_PERSIAN)
    if latin_digits:
        value = value.translate(_DIGIT_TRANSLATION)
    # Keep one ZWNJ when several were accidentally repeated.
    value = re.sub("\u200c{2,}", "\u200c", value)
    return value


def normalize_for_comparison(text: str) -> str:
    """Normalize Persian variants and collapse whitespace without removing ZWNJ."""
    return _WHITESPACE.sub(" ", normalize_persian_text(text)).strip()
