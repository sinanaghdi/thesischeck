"""Pydantic schemas for validated ruleset configuration."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LocalizedText(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fa: str
    en: str


class RuleDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")
    title: LocalizedText
    severity: Literal["error", "warning", "info"]
    checker: str
    enabled: bool = True
    parameters: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    explanation: LocalizedText
    how_to_fix: LocalizedText


class RuleSetMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    university: str
    faculty: str
    version: str
    status: Literal["example_unverified", "verified"]
    official_guideline_verified: bool
    warning: LocalizedText


class RuleSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metadata: RuleSetMetadata
    scoring_weights: dict[str, float]
    rules: list[RuleDefinition]

    def validate_scoring_weights(self) -> "RuleSet":
        """Validate weights without implying that they are university policy."""
        if any(value < 0 for value in self.scoring_weights.values()):
            raise ValueError("Scoring weights must be non-negative")
        if self.scoring_weights and abs(sum(self.scoring_weights.values()) - 100.0) > 0.01:
            raise ValueError("Scoring weights must sum to 100")
        ids = [rule.id for rule in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("Rule IDs must be unique")
        if (
            self.metadata.status == "verified"
            and not self.metadata.official_guideline_verified
        ):
            raise ValueError("A verified ruleset must declare official guideline verification")
        if (
            self.metadata.status == "example_unverified"
            and self.metadata.official_guideline_verified
        ):
            raise ValueError("An example-unverified ruleset cannot claim official verification")
        return self
