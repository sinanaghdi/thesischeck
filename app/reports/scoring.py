"""Explainable weighted scoring based only on checks that actually ran."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.rules.findings import CheckReport, Finding
from app.rules.schemas import RuleSet
from app.schemas.document import NormalizedDocument


class ScoreCategory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    title_fa: str
    title_en: str
    configured_weight: float
    assessed_weight: float = 0.0
    normalized_weight: float = 0.0
    score: float | None = None
    deduction_points: float = 0.0
    finding_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    checked_rules: int = 0
    skipped_rules: int = 0
    available: bool = False
    explanation_fa: str
    explanation_en: str


class HealthReport(BaseModel):
    """A transparent report object. The score is not an academic grade."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    generated_at: datetime
    file_name: str
    source_format: str
    page_count: int | None = None
    ruleset_name: str
    ruleset_version: str
    ruleset_verified: bool
    score: float | None = Field(default=None, ge=0, le=100)
    score_label_fa: str
    score_label_en: str
    coverage_percent: float = Field(ge=0, le=100)
    configured_weight_total: float
    assessed_weight_total: float
    score_formula_fa: str
    score_formula_en: str
    summary_fa: str
    summary_en: str
    severity_counts: dict[str, int]
    categories: list[ScoreCategory]
    top_issues: list[Finding] = Field(default_factory=list)
    checks: CheckReport
    parser_diagnostics: list[dict[str, str]] = Field(default_factory=list)
    limitations_fa: list[str] = Field(default_factory=list)
    limitations_en: list[str] = Field(default_factory=list)


_CATEGORY_CONFIG: dict[str, dict[str, Any]] = {
    "formatting_structure": {
        "title_fa": "قالب‌بندی و ساختار",
        "title_en": "Formatting and structure",
        "checkers": {
            "docx_body_font", "docx_page_margins", "docx_line_spacing",
            "required_sections", "heading_hierarchy",
        },
        "finding_categories": {"formatting", "structure"},
        "explanation_fa": "بررسی‌های قالب‌بندی تنظیم‌شده و سلسله‌مراتب عنوان‌ها؛ وزن فقط به نسبت قواعد اجراشده محاسبه می‌شود.",
        "explanation_en": "Configured formatting checks and heading hierarchy; weight is prorated to executed rules.",
    },
    "references_citations": {
        "title_fa": "منابع و ارجاعات",
        "title_en": "References and citations",
        "checkers": {"reference_consistency", "reference_parse_diagnostics"},
        "finding_categories": {"references"},
        "explanation_fa": "تطبیق ابتکاری ارجاعات داخل متن با فهرست منابع.",
        "explanation_en": "Heuristic cross-checks between in-text citations and bibliography entries.",
    },
    "research_traceability": {
        "title_fa": "ردیابی پرسش پژوهش تا نتیجه",
        "title_en": "Research traceability",
        "checkers": {"research_traceability"},
        "finding_categories": {"research_traceability"},
        "explanation_fa": "تحلیل ردیابی پژوهش هنوز پیاده‌سازی نشده و امتیاز ندارد.",
        "explanation_en": "Research traceability is not implemented yet and is not scored.",
    },
    "figures_tables_algorithms": {
        "title_fa": "شکل‌ها، جدول‌ها و الگوریتم‌ها",
        "title_en": "Figures, tables and algorithms",
        "checkers": {"figure_table_consistency"},
        "finding_categories": {"figures_tables"},
        "explanation_fa": "بررسی شماره کپشن‌ها و ارجاع‌های متناظر که قابل استخراج بوده‌اند.",
        "explanation_en": "Checks numbering and references for captions detected by the parser.",
    },
    "abstracts_terminology": {
        "title_fa": "چکیده‌ها و یکدستی اصطلاحات",
        "title_en": "Abstracts and terminology",
        "checkers": {"abstract_presence", "abstract_consistency", "terminology_consistency"},
        "finding_categories": {"abstracts", "terminology"},
        "explanation_fa": "بررسی‌های ساختاری چکیده و واژه‌نامهٔ اصطلاحات.",
        "explanation_en": "Abstract-structure checks and glossary-based terminology hints.",
    },
    "writing_quality": {
        "title_fa": "کیفیت نگارش",
        "title_en": "Writing quality",
        "checkers": {"writing_quality"},
        "finding_categories": {"writing_quality"},
        "explanation_fa": "بررسی نگارشی هنوز پیاده‌سازی نشده و امتیاز ندارد.",
        "explanation_en": "Writing-quality analysis is not implemented yet and is not scored.",
    },
}


def build_health_report(
    document: NormalizedDocument,
    checks: CheckReport,
    ruleset: RuleSet,
) -> HealthReport:
    """Build a score with visible penalties and prorated coverage.

    Per-category score = max(0, 100 - errors*12 - warnings*4 - info*1).
    Assessed category weight = configured weight * executed configured rules /
    all configured rules in that score category. The overall score is the
    weighted mean using assessed weights only. Skipped rules do not increase coverage.
    """
    all_weights = ruleset.scoring_weights
    total_weight = float(sum(all_weights.values()))
    results_by_id = {result.rule_id: result for result in checks.results}
    rule_by_id = {rule.id: rule for rule in ruleset.rules}
    categories: list[ScoreCategory] = []

    for key, config in _CATEGORY_CONFIG.items():
        configured_weight = float(all_weights.get(key, 0.0))
        member_rules = [rule for rule in ruleset.rules if rule.checker in config["checkers"]]
        member_results = [
            results_by_id[rule.id] for rule in member_rules if rule.id in results_by_id
        ]
        ran_results = [
            result for result in member_results
            if result.status in {"passed", "issues_found"}
        ]
        relevant_findings = [
            finding for finding in checks.findings
            if finding.category in config["finding_categories"]
            or (
                finding.rule_id in rule_by_id
                and rule_by_id[finding.rule_id].checker in config["checkers"]
            )
        ]
        severity_counts = {
            severity: sum(1 for item in relevant_findings if item.severity == severity)
            for severity in ("error", "warning", "info")
        }
        deduction = min(
            100.0,
            severity_counts["error"] * 12.0
            + severity_counts["warning"] * 4.0
            + severity_counts["info"] * 1.0,
        )
        assessed_weight = (
            configured_weight * len(ran_results) / len(member_rules)
            if configured_weight > 0 and member_rules and ran_results
            else 0.0
        )
        available = assessed_weight > 0
        category_score = round(max(0.0, 100.0 - deduction), 1) if available else None
        categories.append(
            ScoreCategory(
                key=key,
                title_fa=config["title_fa"],
                title_en=config["title_en"],
                configured_weight=configured_weight,
                assessed_weight=round(assessed_weight, 2),
                score=category_score,
                deduction_points=round(deduction, 1),
                finding_count=len(relevant_findings),
                error_count=severity_counts["error"],
                warning_count=severity_counts["warning"],
                info_count=severity_counts["info"],
                checked_rules=len(ran_results),
                skipped_rules=sum(1 for result in member_results if result.status == "skipped"),
                available=available,
                explanation_fa=config["explanation_fa"],
                explanation_en=config["explanation_en"],
            )
        )

    assessed_weight_total = sum(category.assessed_weight for category in categories)
    for category in categories:
        category.normalized_weight = (
            round(category.assessed_weight / assessed_weight_total * 100.0, 2)
            if category.available and assessed_weight_total > 0
            else 0.0
        )
    score = None
    if assessed_weight_total > 0:
        score = round(
            sum(
                (category.score or 0.0) * category.assessed_weight
                for category in categories if category.available
            ) / assessed_weight_total,
            1,
        )
    coverage = (
        round(assessed_weight_total / total_weight * 100.0, 1)
        if total_weight > 0 else 0.0
    )
    severity_counts = {
        severity: sum(1 for item in checks.findings if item.severity == severity)
        for severity in ("error", "warning", "info")
    }
    active_categories = [category for category in categories if category.available]
    if score is None:
        summary_fa = "برای محاسبه امتیاز، هیچ دستهٔ امتیازدهی فعال و قابل اجرا نبود."
        summary_en = "No scoring category was configured and successfully executed."
    else:
        summary_fa = (
            f"امتیاز موقت {score:.1f} از ۱۰۰ بر اساس {len(active_categories)} دستهٔ قابل ارزیابی "
            f"محاسبه شد؛ پوشش وزن‌های امتیازدهی {coverage:.1f}٪ است."
        )
        summary_en = (
            f"Provisional score: {score:.1f}/100 across {len(active_categories)} assessed categories; "
            f"weighted coverage is {coverage:.1f}%."
        )

    limitations_fa = [
        "این امتیاز نمره دانشگاهی یا تضمین کیفیت علمی نیست.",
        "وزن هر دسته به نسبت قواعدی که واقعاً اجرا شده‌اند محاسبه شده است؛ قواعد ردشده پوشش ایجاد نمی‌کنند.",
        "یافته‌های منابع، اصطلاحات و ساختار ابتکاری‌اند و باید با سند اصلی بازبینی شوند.",
    ]
    limitations_en = [
        "This score is not an academic grade or a guarantee of scientific quality.",
        "Each category's assessed weight is proportional to the rules that actually ran; skipped rules do not count toward coverage.",
        "Reference, terminology and structure findings are heuristic and require human review.",
    ]
    if not checks.ruleset_verified:
        limitations_fa.insert(0, "مجموعه قواعد قالب‌بندی رسمی دانشگاه تأیید نشده است.")
        limitations_en.insert(0, "The university formatting ruleset is not verified.")
    if document.source_format == "pdf":
        limitations_fa.append("بررسی قلم و تنظیمات اصلی Word از PDF در دسترس نیست.")
        limitations_en.append("Original Word font and page-setup checks are unavailable for PDF input.")

    return HealthReport(
        generated_at=datetime.now(UTC),
        file_name=document.file_name,
        source_format=document.source_format,
        page_count=document.page_count,
        ruleset_name=checks.ruleset_name,
        ruleset_version=checks.ruleset_version,
        ruleset_verified=checks.ruleset_verified,
        score=score,
        score_label_fa="امتیاز موقت سلامت نگارش/قالب" if score is not None else "امتیاز در دسترس نیست",
        score_label_en="Provisional writing/format health score" if score is not None else "Score unavailable",
        coverage_percent=coverage,
        configured_weight_total=round(total_weight, 2),
        assessed_weight_total=round(assessed_weight_total, 2),
        score_formula_fa=(
            "امتیاز هر دسته = ۱۰۰ − (یافته مهم × ۱۲ + بازبینی × ۴ + اطلاعات × ۱)، حداقل صفر. "
            "وزن سنجیده‌شدهٔ دسته = وزن تنظیم‌شده × تعداد قواعد اجراشده / تعداد قواعد تنظیم‌شده "
            "در آن دسته. امتیاز کل میانگین وزنی با وزن سنجیده‌شده است؛ قواعد ردشده پوشش ایجاد نمی‌کنند."
        ),
        score_formula_en=(
            "Category score = max(0, 100 − errors×12 − warnings×4 − info×1). "
            "Assessed category weight = configured weight × executed rules / configured rules in "
            "that category. Overall score is the weighted mean using assessed weights only; skipped "
            "rules do not increase coverage."
        ),
        summary_fa=summary_fa,
        summary_en=summary_en,
        severity_counts=severity_counts,
        categories=categories,
        top_issues=checks.findings[:10],
        checks=checks,
        parser_diagnostics=[
            {
                "code": diagnostic.code,
                "message": diagnostic.message,
                "severity": diagnostic.severity,
            }
            for diagnostic in document.diagnostics
        ],
        limitations_fa=limitations_fa,
        limitations_en=limitations_en,
    )
