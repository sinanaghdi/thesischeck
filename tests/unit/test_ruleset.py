from pathlib import Path

import pytest

from app.rules.loader import load_ruleset
from app.rules.schemas import RuleSet


def test_example_ruleset_is_prominently_unverified() -> None:
    root = Path(__file__).resolve().parents[2]
    ruleset = load_ruleset(root / "rulesets" / "mazandaran_engineering_example.yaml")
    assert ruleset.metadata.status == "example_unverified"
    assert ruleset.metadata.official_guideline_verified is False
    assert any(not rule.enabled for rule in ruleset.rules if rule.id.startswith("FORMAT_"))


def test_score_weights_must_sum_to_one_hundred() -> None:
    raw = {
        "metadata": {
            "name": "example",
            "university": "example",
            "faculty": "example",
            "version": "1",
            "status": "example_unverified",
            "official_guideline_verified": False,
            "warning": {"fa": "هشدار", "en": "Warning"},
        },
        "scoring_weights": {"one": 90},
        "rules": [],
    }
    with pytest.raises(ValueError, match="sum to 100"):
        RuleSet.model_validate(raw).validate_scoring_weights()
