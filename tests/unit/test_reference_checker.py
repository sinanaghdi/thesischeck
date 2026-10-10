from app.rules.checkers.references import (
    check_reference_consistency,
    expand_numeric_group,
)
from app.rules.loader import load_ruleset
from app.schemas.document import DocumentElement, NormalizedDocument

ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]


def element(element_id: str, kind: str, text: str, index: int, level: int | None = None):
    return DocumentElement(
        element_id=element_id,
        kind=kind,
        text=text,
        normalized_text=text,
        heading_level=level,
        heading_path=[text] if kind == "heading" else [],
        source_index=index,
    )


def crosscheck_rule():
    ruleset = load_ruleset(ROOT / "rulesets" / "mazandaran_engineering_example.yaml")
    return next(rule for rule in ruleset.rules if rule.id == "REFERENCES_CROSSCHECK")


def test_expands_ieee_groups_ranges_and_persian_digits():
    assert expand_numeric_group("1, 3-5، ۷") == [1, 3, 4, 5, 7]
    assert expand_numeric_group("3–5") == [3, 4, 5]


def test_crosschecks_square_bracket_range_with_separate_brackets():
    entries = [
        element("p1", "paragraph", "Prior work is numbered [1]-[3], with additional work [5,7].", 0),
        element("h1", "heading", "References", 1, 1),
        element("r1", "paragraph", "[1] Example Alpha. Journal, 2020.", 2),
        element("r2", "paragraph", "[2] Example Beta. Journal, 2021.", 3),
        element("r3", "paragraph", "[3] Example Gamma. Journal, 2022.", 4),
        element("r5", "paragraph", "[5] Example Epsilon. Journal, 2023.", 5),
        element("r7", "paragraph", "[7] Example Eta. Journal, 2024.", 6),
    ]
    document = NormalizedDocument(
        source_format="docx", file_name="synthetic.docx", elements=entries, parsing_complete=True
    )
    findings = check_reference_consistency(document, crosscheck_rule())
    assert not any("no matching numbered reference" in item.message_en for item in findings)
    assert not any("was not found in the detected" in item.message_en for item in findings)
    assert any("gap at 4" in item.message_en for item in findings)


def test_reports_citation_missing_from_reference_list():
    entries = [
        element("p1", "paragraph", "See [1] and [4] for this synthetic claim.", 0),
        element("h1", "heading", "References", 1, 1),
        element("r1", "paragraph", "[1] A valid-looking synthetic reference, 2020.", 2),
    ]
    document = NormalizedDocument(
        source_format="docx", file_name="synthetic.docx", elements=entries, parsing_complete=True
    )
    findings = check_reference_consistency(document, crosscheck_rule())
    assert any("Numeric citation [4]" in item.message_en for item in findings)
    assert all(item.snippet is not None for item in findings)


def test_detects_duplicate_numbering_and_probable_duplicate_entries():
    entries = [
        element("p1", "paragraph", "Cited material [1] in body.", 0),
        element("h1", "heading", "References", 1, 1),
        element("r1", "paragraph", "[1] Example title. Journal of Testing, 2020.", 2),
        element("r2", "paragraph", "[1] Example title. Journal of Testing, 2020.", 3),
    ]
    document = NormalizedDocument(
        source_format="docx", file_name="synthetic.docx", elements=entries, parsing_complete=True
    )
    findings = check_reference_consistency(document, crosscheck_rule())
    assert any("appears more than once" in item.message_en for item in findings)
