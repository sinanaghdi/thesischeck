from app.parsing.normalization import normalize_for_comparison, normalize_persian_text


def test_arabic_yeh_and_kaf_are_normalized() -> None:
    assert normalize_for_comparison("يادگيرى ك") == "یادگیری ک"


def test_persian_and_arabic_digits_become_ascii_for_comparison() -> None:
    assert normalize_persian_text("۱۲۳ ١٢٣") == "123 123"


def test_zwnj_is_preserved_and_duplicate_zwnj_collapsed() -> None:
    assert normalize_for_comparison("می\u200c\u200cرود") == "می\u200cرود"


def test_whitespace_is_collapsed_without_removing_word_boundary() -> None:
    assert normalize_for_comparison("  متن\n   نمونه  ") == "متن نمونه"
