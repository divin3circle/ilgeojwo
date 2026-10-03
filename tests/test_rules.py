import json

import pytest

from ilgeojwo.config import load_config
from ilgeojwo.risk.rules import load_rules


def test_the_shipped_rule_file_loads():
    rules = load_rules(load_config(env={}).rules_path)
    assert len(rules) >= 4
    assert {"nsaid", "decongestant", "beta_blocker", "sedating_antihistamine"} <= {
        r.id for r in rules}


def test_every_rule_carries_a_citation():
    """Global Constraint: an uncited medical warning is not shippable."""
    for r in load_rules(load_config(env={}).rules_path):
        assert r.source.strip(), f"rule {r.id} has no source"


def test_every_rule_tells_her_to_ask_a_human():
    """Spec §5.4: the tool flags and defers. It never recommends alone."""
    for r in load_rules(load_config(env={}).rules_path):
        assert "pharmacist" in r.message_en.lower() or "doctor" in r.message_en.lower()


def test_a_rule_missing_a_source_is_rejected_loudly(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"profile": "x", "rules": [
        {"id": "a", "severity": "high", "match_ko": ["가"], "match_en": [],
         "message_en": "ask the pharmacist", "source": ""}]}))
    with pytest.raises(ValueError, match="source"):
        load_rules(bad)


def test_a_rule_with_no_patterns_is_rejected(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"profile": "x", "rules": [
        {"id": "a", "severity": "high", "match_ko": [], "match_en": [],
         "message_en": "ask the pharmacist", "source": "s"}]}))
    with pytest.raises(ValueError, match="pattern"):
        load_rules(bad)
