import unicodedata

import pytest

from ilgeojwo.config import load_config
from ilgeojwo.risk.matcher import match_risks
from ilgeojwo.risk.rules import Rule, load_rules

RULES = load_rules(load_config(env={}).rules_path)
ALL_PATTERNS = [(r.id, p) for r in RULES for p in (*r.match_ko, *r.match_en)]


def ids(ws):
    return {w.rule_id for w in ws}


def test_a_korean_ingredient_name_fires_its_rule():
    assert "nsaid" in ids(match_risks(["이부프로펜"], "", RULES))


def test_an_english_ingredient_name_fires_its_rule():
    assert "nsaid" in ids(match_risks(["Ibuprofen 200mg"], "", RULES))


def test_a_pattern_present_only_in_raw_ocr_text_still_fires():
    """Spec §5.2 — THE property that makes this safe. The model missed the
    ingredient entirely; the raw text must still raise the warning."""
    ws = match_risks([], "타이레놀콜드 성분: 이부프로펜 200mg 슈도에페드린", RULES)
    assert "nsaid" in ids(ws)
    assert "decongestant" in ids(ws)
    assert any("ocr_text" in w.found_in for w in ws)


@pytest.mark.parametrize("rule_id,pattern", ALL_PATTERNS,
                         ids=[f"{i}:{p}" for i, p in ALL_PATTERNS])
def test_every_shipped_pattern_fires_its_own_rule(rule_id, pattern):
    """Review I15: the §5.2 property was demonstrated by one example. This
    proves no shipped pattern is dead, so a future edit cannot quietly add an
    unmatchable one."""
    assert rule_id in ids(match_risks([], f"성분: {pattern} 100mg", RULES))


def test_a_wrong_extracted_ingredient_list_cannot_suppress_a_raw_text_hit():
    """Review I15(b): the model confidently reporting the wrong thing must not
    mask what is actually printed."""
    ws = match_risks(["아세트아미노펜 500mg"], "성분: 이부프로펜 200mg", RULES)
    assert "nsaid" in ids(ws)


@pytest.mark.parametrize("raw", [
    "성분\n이부\n프로펜\n200mg",
    "성분 이부-\n프로펜 200mg",
    "성분 이부­프로펜",
    "성분 이부·프로펜",
    "성분 이 부 프 로 펜",
    "성분 이부​프로펜",
    "성분 이부﻿프로펜",
    "성분 ＩＢＵＰＲＯＦＥＮ ２００ｍｇ",
])
def test_ocr_mangling_never_hides_a_high_severity_warning(raw):
    """Review C1/C2/C3 end to end through the matcher."""
    assert "nsaid" in ids(match_risks([], raw, RULES))


def test_decomposed_hangul_does_not_hide_a_warning():
    assert "nsaid" in ids(match_risks([], unicodedata.normalize("NFD", "이부프로펜"), RULES))


@pytest.mark.parametrize("ingredient,expected", [
    ("디히드로코데인", "opioid_antitussive"),
    ("인산코데인", "opioid_antitussive"),
    ("트리프롤리딘", "sedating_antihistamine"),
    ("아세클로페낙", "nsaid"),
    ("케토프로펜", "nsaid"),
    ("피록시캄", "nsaid"),
    ("자일로메타졸린", "decongestant"),
    ("카르테올롤", "beta_blocker"),
    ("이소프로필안티피린", "pyrazolone"),
    ("아황산염", "sulfite"),
])
def test_the_classes_a_respiratory_patient_meets_in_a_korean_pharmacy(ingredient, expected):
    """Review C6/I14: coverage gaps found by the reviewer, each pinned."""
    assert expected in ids(match_risks([ingredient], "", RULES))


@pytest.mark.parametrize("brand,expected", [
    ("부루펜", "nsaid"),
    ("게보린", "pyrazolone"),
    ("사리돈", "pyrazolone"),
    ("판콜에이", "decongestant"),
])
def test_a_front_panel_brand_photo_is_not_silently_cleared(brand, expected):
    """Review I10: a pharmacy hand-over photographed front-first shows a brand
    and no ingredient panel. Returning no warnings there is indistinguishable
    from 'cleared'."""
    assert expected in ids(match_risks([], brand, RULES))


def test_plain_tylenol_is_not_flagged():
    """The brand patterns must not swallow plain acetaminophen."""
    assert match_risks(["아세트아미노펜 500mg"], "타이레놀 500mg 아세트아미노펜", RULES) == []


def test_a_contraindication_paragraph_still_fires_but_this_is_a_known_false_positive():
    """Spec §5.2 accepts false positives. Korean boxes name other drugs in their
    주의사항 paragraph, so this fires on a safe box — which is why no message
    claims the box CONTAINS the ingredient (see test_rules.py)."""
    box = ("타이레놀 500mg 성분: 아세트아미노펜 500mg\n"
           "주의사항: 이부프로펜 등 다른 해열진통제와 함께 복용하지 마십시오.")
    assert "nsaid" in ids(match_risks(["아세트아미노펜 500mg"], box, RULES))


def test_vitamins_produce_no_warnings():
    assert match_risks(["비타민C"], "비타민C 1000mg 아스코르브산", RULES) == []


def test_warnings_are_ordered_most_severe_first():
    ws = match_risks([], "클로르페니라민 이부프로펜 슈도에페드린", RULES)
    order = {"high": 0, "medium": 1, "low": 2}
    assert [order[w.severity] for w in ws] == sorted(order[w.severity] for w in ws)
    assert ws[0].severity == "high"


def test_an_unrecognised_severity_sorts_first_not_last():
    """Review C4: load_rules now rejects these, but if one ever slips through,
    the worst case must be over-prominence, never burial below 'low'."""
    odd = Rule("odd", "critical", ("이부프로펜",), (), "ask the pharmacist", "s")
    low = Rule("lo", "low", ("아황산염",), (), "ask the pharmacist", "s")
    ws = match_risks([], "이부프로펜 아황산염", (low, odd))
    assert [w.rule_id for w in ws] == ["odd", "lo"]


def test_matched_names_every_hit_so_she_can_check_them_all():
    """Review I8: the message says she can verify it; one name of three is not
    enough to verify."""
    w = match_risks([], "성분: 이부프로펜 200mg, 아스피린 100mg, 나프록센 250mg", RULES)[0]
    assert set(w.matched) >= {"이부프로펜", "아스피린", "나프록센"}


def test_found_in_reports_both_sources_when_both_saw_it():
    """Review I9: the §5.2 story is two independent readers; the card should be
    able to say whether both agreed."""
    w = match_risks(["이부프로펜"], "성분 이부프로펜 200mg", RULES)[0]
    assert set(w.found_in) == {"ingredients", "ocr_text"}


def test_each_warning_tells_her_to_ask_a_human():
    w = match_risks(["이부프로펜"], "", RULES)[0]
    assert "pharmacist" in w.message.lower() or "doctor" in w.message.lower()


def test_a_rule_fires_at_most_once_even_with_several_matches():
    ws = match_risks(["이부프로펜", "아스피린"], "이부프로펜 아스피린 나프록센", RULES)
    assert len([w for w in ws if w.rule_id == "nsaid"]) == 1


def test_adjacent_ingredient_entries_do_not_fuse_into_a_phantom():
    """Review M1: joining with a space then stripping all whitespace invented
    '에페드린' out of two harmless fragments."""
    assert match_risks(["에", "페드린"], "", RULES) == []


@pytest.mark.parametrize("ingredients,raw", [
    (None, ""), ([], None), ([None], ""), ([200], ""), (None, None),
    ([["nested"]], ""), ("이부프로펜", ""),
])
def test_bad_inputs_do_not_crash_the_safety_module(ingredients, raw):
    """Review I13: a crash here is a 500 with zero warnings — it fails unsafe."""
    assert isinstance(match_risks(ingredients, raw, RULES), list)


def test_a_null_ingredient_list_still_screens_the_raw_text():
    assert "nsaid" in ids(match_risks(None, "성분 이부프로펜", RULES))


def test_the_matcher_imports_nothing_that_could_reach_the_world():
    """Spec §5.1: it is pure logic, which is why it can be trusted.

    The previous version of this test grepped the module's own source text for
    'urllib', which made it self-referential and blind to transitive imports.
    This inspects the import graph instead.
    """
    import ast
    import pathlib

    from ilgeojwo.risk import matcher
    tree = ast.parse(pathlib.Path(matcher.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert imported <= {"__future__", "dataclasses", "normalize", "rules"}, imported


@pytest.mark.parametrize("misread,expected", [
    ("이부프로팬", "nsaid"),                    # 펜 -> 팬
    ("이부프로텐", "nsaid"),
    ("아스피릭", "nsaid"),
    ("슈도에폐드린", "decongestant"),            # 페 -> 폐
    ("클로르페니라빈", "sedating_antihistamine"),
    ("디히드로코데임", "opioid_antitussive"),
    ("ibuprofan", "nsaid"),
])
def test_a_single_syllable_misread_still_raises_an_approximate_warning(misread, expected):
    """MEASURED, not hypothetical: on a clean synthetic render EasyOCR
    substituted 허->히, 를->클 and 납->남. Exact matching alone would drop the
    warning for a box that really does contain the ingredient."""
    ws = match_risks([], f"성분: {misread} 200mg", RULES)
    assert expected in ids(ws)
    assert next(w for w in ws if w.rule_id == expected).approximate is True


def test_an_exact_match_is_never_marked_approximate():
    assert match_risks([], "성분: 이부프로펜 200mg", RULES)[0].approximate is False


def test_an_exact_hit_wins_over_an_approximate_one_for_the_same_rule():
    ws = match_risks([], "이부프로팬 그리고 아스피린 100mg", RULES)
    assert next(w for w in ws if w.rule_id == "nsaid").approximate is False


def test_short_names_are_exact_only_so_the_tool_does_not_cry_wolf():
    """One changed character in a three-syllable name is too weak a signal to
    act on. Longer spellings of the same drug still carry it."""
    assert match_risks([], "성분: 코데임", RULES) == []
    assert "opioid_antitussive" in ids(match_risks([], "성분: 인산코데임", RULES))


def test_fuzzy_matching_does_not_drag_in_a_safe_box():
    assert match_risks(["아세트아미노펜 500mg"], "타이레놀 아세트아미노펜 500mg", RULES) == []


def test_fuzzy_matching_does_not_drag_in_vitamins():
    assert match_risks(["비타민C"], "비타민C 1000mg 아스코르브산", RULES) == []
