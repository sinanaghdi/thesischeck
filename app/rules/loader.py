"""Safe YAML ruleset loader. The checker field is data, never a Python import path."""

from pathlib import Path

import yaml

from app.rules.schemas import RuleSet


def load_ruleset(path: str | Path) -> RuleSet:
    """Load and validate a ruleset from YAML."""
    ruleset_path = Path(path)
    with ruleset_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if not isinstance(raw, dict):
        raise ValueError("Ruleset root must be a YAML mapping")
    ruleset = RuleSet.model_validate(raw)
    return ruleset.validate_scoring_weights()
