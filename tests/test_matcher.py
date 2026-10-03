from ilgeojwo.config import load_config
from ilgeojwo.risk.matcher import match_risks
from ilgeojwo.risk.rules import load_rules

RULES = load_rules(load_config(env={}).rules_path)


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
    assert any(w.found_in == "ocr_text" for w in ws)


def test_a_name_broken_by_an_ocr_line_break_still_fires():
    """Review Focus 3, end to end through the matcher."""
    assert "nsaid" in ids(match_risks([], "성분\n이부\n프로펜\n200mg", RULES))


def test_ocr_spacing_noise_does_not_hide_a_warning():
    assert "nsaid" in ids(match_risks([], "이 부 프 로 펜", RULES))


def test_decomposed_hangul_does_not_hide_a_warning():
    import unicodedata
    assert "nsaid" in ids(match_risks([], unicodedata.normalize("NFD", "이부프로펜"), RULES))


def test_a_safe_product_produces_no_warnings():
    assert match_risks(["아세트아미노펜"], "아세트아미노펜 500mg 타이레놀", RULES) == []


def test_vitamins_produce_no_warnings():
    assert match_risks(["비타민C"], "비타민C 1000mg 아스코르브산", RULES) == []


def test_warnings_are_ordered_most_severe_first():
    ws = match_risks([], "클로르페니라민 이부프로펜 슈도에페드린", RULES)
    assert [w.severity for w in ws] == ["high", "medium", "low"]


def test_each_warning_names_what_matched_so_she_can_check_it_herself():
    w = match_risks(["이부프로펜"], "", RULES)[0]
    assert w.matched == "이부프로펜"
    assert "pharmacist" in w.message.lower()


def test_a_rule_fires_at_most_once_even_with_several_matches():
    ws = match_risks(["이부프로펜", "아스피린"], "이부프로펜 아스피린 나프록센", RULES)
    assert len([w for w in ws if w.rule_id == "nsaid"]) == 1


def test_the_matcher_needs_no_model_and_no_network():
    """Spec §5.1: it is pure logic, which is why it can be trusted."""
    import inspect

    from ilgeojwo.risk import matcher
    src = inspect.getsource(matcher)
    for forbidden in ("urllib", "requests", "httpx", "ollama", "transformers", "open("):
        assert forbidden not in src
