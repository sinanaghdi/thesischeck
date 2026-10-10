from pathlib import Path

from app.rules.checkers.abstracts import check_abstract_consistency, check_abstract_presence
from app.rules.checkers.figures_tables import check_figure_table_consistency
from app.rules.loader import load_ruleset
from app.schemas.document import DocumentElement, NormalizedDocument

ROOT = Path(__file__).resolve().parents[2]


def element(
    element_id: str, kind: str, text: str, index: int, level: int | None = None, **metadata
):
    return DocumentElement(
        element_id=element_id,
        kind=kind,
        text=text,
        normalized_text=text,
        heading_level=level,
        heading_path=[text] if kind == "heading" else [],
        source_index=index,
        metadata=metadata,
    )


def rules():
    ruleset = load_ruleset(ROOT / "rulesets" / "mazandaran_engineering_example.yaml")
    return {item.id: item for item in ruleset.rules}


def test_detects_keyword_count_mismatch_between_abstracts():
    document = NormalizedDocument(
        source_format="docx",
        file_name="synthetic.docx",
        parsing_complete=True,
        elements=[
            element("h1", "heading", "چکیده", 0, 1),
            element("p1", "paragraph", "این متن آزمایشی چکیده فارسی برای بررسی خودکار ساختار و طول متن است.", 1),
            element("p2", "paragraph", "واژگان کلیدی: مدل، دقت", 2),
            element("h2", "heading", "Abstract", 3, 1),
            element("p3", "paragraph", "This synthetic abstract provides an example method and results to test the heuristic checker without making a scientific claim.", 4),
            element("p4", "paragraph", "Keywords: model, accuracy, dataset", 5),
        ],
    )
    available = rules()
    assert not check_abstract_presence(document, available["ABSTRACT_BOTH_LANGUAGES"])
    findings = check_abstract_consistency(document, available["ABSTRACT_CONSISTENCY"])
    assert any("Keyword counts differ" in item.message_en for item in findings)


def test_detects_reference_to_missing_table_caption():
    document = NormalizedDocument(
        source_format="docx",
        file_name="synthetic.docx",
        parsing_complete=True,
        elements=[
            element("h1", "heading", "Chapter 1", 0, 1),
            element("p1", "paragraph", "شکل 1-1 معماری نمونه", 1, is_caption=True, caption_number="1-1", caption_label="شکل"),
            element("p2", "paragraph", "نتیجه در شکل 1-1 دیده می‌شود، اما جدول 9 وجود ندارد.", 2),
        ],
    )
    findings = check_figure_table_consistency(document, rules()["FIGURE_TABLE_CROSSCHECK"])
    assert any("table 9" in item.message_en.lower() for item in findings)
    assert not any("caption “شکل 1-1”" in item.message_en for item in findings)
