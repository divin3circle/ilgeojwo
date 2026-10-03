import json

import pytest

from ilgeojwo.config import load_config
from ilgeojwo.risk.rules import load_rules

SHIPPED = load_config(env={}).rules_path

OK_RULE = {
    "id": "a", "severity": "high", "match_ko": ["이부프로펜"], "match_en": ["ibuprofen"],
    "message_en": "An NSAID name appears here. Ask the pharmacist.", "source": "s",
}


def _write(tmp_path, rules, **top):
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"profile": "respiratory", "rules": rules, **top},
                            ensure_ascii=False), encoding="utf-8")
    return p


def test_the_shipped_rule_file_loads():
    rules = load_rules(SHIPPED)
    assert len(rules) >= 4
    assert {"nsaid", "decongestant", "beta_blocker", "sedating_antihistamine"} <= {
        r.id for r in rules}


def test_the_shipped_file_covers_opioid_cough_suppressants():
    """Review C6: dihydrocodeine is in Korean OTC cough medicine, and opioid
    respiratory depression is the most direct harm this tool exists to flag."""
    assert "opioid_antitussive" in {r.id for r in load_rules(SHIPPED)}


def test_every_rule_carries_a_citation():
    for r in load_rules(SHIPPED):
        assert r.source.strip(), f"rule {r.id} has no source"


def test_every_rule_tells_her_to_ask_a_human():
    """Spec §5.4: the tool flags and defers. It never recommends alone."""
    for r in load_rules(SHIPPED):
        assert "pharmacist" in r.message_en.lower() or "doctor" in r.message_en.lower()


def test_no_message_asserts_that_the_box_contains_the_ingredient():
    """Review I7: a Korean box names other drugs in its contraindication
    paragraph, so a match does not prove containment. Claiming it does on a
    Tylenol box is the trust erosion that makes her stop reading warnings."""
    for r in load_rules(SHIPPED):
        low = r.message_en.lower()
        for claim in ("contains an", "contains a ", "contains the"):
            assert claim not in low, f"rule {r.id} asserts containment: {r.message_en!r}"


def test_a_valid_minimal_file_loads(tmp_path):
    assert len(load_rules(_write(tmp_path, [OK_RULE]))) == 1


def test_an_empty_rule_list_is_rejected(tmp_path):
    """Review C5: an empty list silently disables every warning."""
    with pytest.raises(ValueError, match="empty|no rules"):
        load_rules(_write(tmp_path, []))


def test_a_missing_rules_key_is_rejected(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"profile": "x"}), encoding="utf-8")
    with pytest.raises(ValueError, match="rules"):
        load_rules(p)


def test_match_ko_as_a_bare_string_is_rejected(tmp_path):
    """Review C5: one missing '[' turns a rule into per-character patterns,
    which then fire on almost any Korean text."""
    bad = {**OK_RULE, "match_ko": "이부프로펜"}
    with pytest.raises(ValueError, match="list"):
        load_rules(_write(tmp_path, [bad]))


def test_match_ko_as_a_dict_is_rejected(tmp_path):
    bad = {**OK_RULE, "match_ko": {"a": "이부프로펜"}}
    with pytest.raises(ValueError, match="list"):
        load_rules(_write(tmp_path, [bad]))


def test_an_unrecognised_severity_is_rejected(tmp_path):
    """Review C4: she is invited to edit this file; 'critical' must not load."""
    for bad_severity in ("critical", "High", "urgent", 1):
        bad = {**OK_RULE, "severity": bad_severity}
        with pytest.raises(ValueError, match="severity"):
            load_rules(_write(tmp_path, [bad]))


def test_a_missing_severity_names_the_offending_rule(tmp_path):
    """Review I12: KeyError('severity') is not actionable for her."""
    bad = {k: v for k, v in OK_RULE.items() if k != "severity"}
    with pytest.raises(ValueError, match="severity"):
        load_rules(_write(tmp_path, [bad]))


def test_an_empty_message_is_rejected(tmp_path):
    for empty in ("", "   ", None):
        bad = {**OK_RULE, "message_en": empty}
        with pytest.raises(ValueError, match="message"):
            load_rules(_write(tmp_path, [bad]))


def test_a_null_source_is_rejected_as_a_value_error_not_an_attribute_error(tmp_path):
    bad = {**OK_RULE, "source": None}
    with pytest.raises(ValueError, match="source"):
        load_rules(_write(tmp_path, [bad]))


def test_duplicate_rule_ids_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="duplicate"):
        load_rules(_write(tmp_path, [OK_RULE, {**OK_RULE}]))


def test_a_rule_with_no_patterns_is_rejected(tmp_path):
    bad = {**OK_RULE, "match_ko": [], "match_en": []}
    with pytest.raises(ValueError, match="pattern"):
        load_rules(_write(tmp_path, [bad]))


def test_a_whitespace_only_pattern_is_rejected(tmp_path):
    """Review I11: ' ' normalises to '', and '' is a substring of every string,
    so it becomes a rule that fires on literally anything."""
    for junk in ([" "], ["​"], ["-"], ["·"]):
        bad = {**OK_RULE, "match_ko": junk, "match_en": []}
        with pytest.raises(ValueError, match="pattern"):
            load_rules(_write(tmp_path, [bad]))


def test_a_non_string_pattern_is_rejected(tmp_path):
    bad = {**OK_RULE, "match_ko": [200], "match_en": []}
    with pytest.raises(ValueError, match="pattern"):
        load_rules(_write(tmp_path, [bad]))


def test_a_non_string_id_is_rejected(tmp_path):
    bad = {**OK_RULE, "id": 7}
    with pytest.raises(ValueError, match="id"):
        load_rules(_write(tmp_path, [bad]))


def test_a_no_fuzzy_entry_that_is_not_one_of_the_rule_patterns_is_rejected(tmp_path):
    """A typo here silently removes protection, so it must fail loudly."""
    bad = {**OK_RULE, "no_fuzzy": ["존재하지않는패턴"]}
    with pytest.raises(ValueError, match="no_fuzzy"):
        load_rules(_write(tmp_path, [bad]))


def test_a_force_fuzzy_entry_that_is_not_one_of_the_rule_patterns_is_rejected(tmp_path):
    bad = {**OK_RULE, "force_fuzzy": ["존재하지않는패턴"]}
    with pytest.raises(ValueError, match="force_fuzzy"):
        load_rules(_write(tmp_path, [bad]))


def test_a_pattern_cannot_be_both_forced_and_forbidden(tmp_path):
    bad = {**OK_RULE, "no_fuzzy": ["이부프로펜"], "force_fuzzy": ["이부프로펜"]}
    with pytest.raises(ValueError, match="both"):
        load_rules(_write(tmp_path, [bad]))


def test_the_shipped_file_exempts_the_noisy_compound_families():
    by_id = {r.id: r for r in load_rules(SHIPPED)}
    assert "이산화황" in by_id["sulfite"].no_fuzzy
    assert "sulfite" in by_id["sulfite"].no_fuzzy


def test_the_shipped_file_forces_fuzzy_on_the_short_high_stakes_names():
    by_id = {r.id: r for r in load_rules(SHIPPED)}
    assert "코데인" in by_id["opioid_antitussive"].force_fuzzy
    assert "티몰롤" in by_id["beta_blocker"].force_fuzzy
