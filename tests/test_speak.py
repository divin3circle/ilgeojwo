"""The counter moment: she cannot speak Korean, the pharmacist cannot read English.

Every phrase is in the rule file, so this works with the network off and with no
model loaded, and says the same thing every time.
"""

from ilgeojwo.config import load_config
from ilgeojwo.risk.rules import load_rules
from ilgeojwo.speak import phrases_for

RULES = load_rules(load_config(env={}).rules_path)


def test_there_is_always_something_to_show_even_before_any_scan():
    said = phrases_for([], RULES)
    assert said.condition_ko
    assert "폐" in said.condition_ko or "천식" in said.condition_ko
    assert said.opening_ko


def test_a_flagged_box_produces_the_question_to_ask_about_it():
    said = phrases_for(["nsaid"], RULES)
    joined = " ".join(said.questions_ko)
    assert "소염진통제" in joined
    assert len(said.questions_ko) == 1


def test_each_question_is_paired_with_what_it_says_in_english():
    """She has to know what she is showing someone before she shows it."""
    said = phrases_for(["nsaid", "opioid_antitussive"], RULES)
    assert len(said.questions_ko) == len(said.questions_en) == 2
    assert all(q.strip() for q in said.questions_en)


def test_unknown_rule_ids_are_ignored_rather_than_crashing():
    assert phrases_for(["not_a_rule"], RULES).questions_ko == []


def test_every_shipped_rule_can_be_asked_about_at_the_counter():
    for rule in RULES:
        said = phrases_for([rule.id], RULES)
        assert said.questions_ko, f"rule {rule.id} has no Korean question"
        assert said.questions_en, f"rule {rule.id} has no English gloss"


def test_the_phrases_need_no_model_and_no_network():
    import ast
    import pathlib

    from ilgeojwo import speak
    tree = ast.parse(pathlib.Path(speak.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert imported <= {"__future__", "dataclasses", "risk", "typing"}, imported
