"""Common, localized result models for deterministic rules."""

from typing import Literal  # noqa: I001

from pydantic import BaseModel, ConfigDict, Field


Severity = Literal["error", "warning", "info"]
RuleStatus = Literal["passed", "issues_found", "skipped"]


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    category: str
    severity: Severity
    title_fa: str
    title_en: str
    message_fa: str
    message_en: str
    element_id: str | None = None
    heading_path: list[str] = Field(default_factory=list)
    page_number: int | None = None
    snippet: str = ""
    suggested_fix_fa: str
    suggested_fix_en: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class RuleResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    title_fa: str
    title_en: str
    severity: Severity
    status: RuleStatus
    findings_count: int = 0
    note_fa: str = ""
    note_en: str = ""


class CheckReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ruleset_name: str
    ruleset_version: str
    ruleset_verified: bool
    disclaimer_fa: str
    disclaimer_en: str
    rules_checked: int
    rules_skipped: int
    findings: list[Finding] = Field(default_factory=list)
    results: list[RuleResult] = Field(default_factory=list)
