from pathlib import Path

from app.rules.checkers.terminology import check_terminology_consistency, load_glossary
from app.rules.loader import load_ruleset
from app.schemas.document import DocumentElement, NormalizedDocument

ROOT = Path(__file__).resolve().parents[2]


def para(element_id: str, text: str, index: int) -> DocumentElement:
    return DocumentElement(
        element_id=element_id,
        kind="paragraph",
        text=text,
        normalized_text=text,
        source_index=index,
    )


def rule():
    ruleset = load_ruleset(ROOT / "rulesets" / "mazandaran_engineering_example.yaml")
    return next(item for item in ruleset.rules if item.id == "TERMINOLOGY_CONSISTENCY")


def test_glossary_loads_expected_columns_and_common_terms():
    glossary = load_glossary(ROOT / "glossary" / "terms_seed.csv")
    assert any(item["english_term"] == "machine learning" for item in glossary)
    assert all("canonical_fa" in item for item in glossary)


def test_detects_inconsistent_persian_equivalents():
    document = NormalizedDocument(
        source_format="docx",
        file_name="synthetic.docx",
        parsing_complete=True,
        elements=[
            para("p1", "در این پروژه از یادگیری ماشین برای آزمایش استفاده شد.", 0),
            para("p2", "فراگیری ماشین در بخش دوم همان مفهوم را بیان می‌کند.", 1),
        ],
    )
    findings = check_terminology_consistency(
        document, rule(), glossary_path=ROOT / "glossary" / "terms_seed.csv"
    )
    assert any("machine learning" in item.message_en.lower() for item in findings)
    assert all(item.element_id for item in findings)


def test_consistent_term_does_not_trigger_glossary_variant_finding():
    document = NormalizedDocument(
        source_format="docx",
        file_name="synthetic.docx",
        parsing_complete=True,
        elements=[para("p1", "یادگیری ماشین در همه فصل‌ها یکسان نوشته شده است.", 0)],
    )
    findings = check_terminology_consistency(
        document, rule(), glossary_path=ROOT / "glossary" / "terms_seed.csv"
    )
    assert not any("machine learning" in item.message_en.lower() for item in findings)
