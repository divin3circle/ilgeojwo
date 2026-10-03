import io
import json

from fastapi.testclient import TestClient

from ilgeojwo.config import load_config
from ilgeojwo.extract.extractor import extract_label
from ilgeojwo.extract.schema import LABEL_ABSENT
from ilgeojwo.risk.rules import load_rules
from ilgeojwo.web.app import create_app

RULES = load_rules(load_config(env={}).rules_path)


class FakeLlm:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts = []

    def complete(self, p):
        self.prompts.append(p)
        return self.replies.pop(0) if self.replies else "{}"


COLD = json.dumps({"product_name": "Tylenol Cold S", "kind": "medicine",
                   "ingredients_ko": ["이부프로펜", "슈도에페드린"],
                   "ingredients": ["ibuprofen", "pseudoephedrine"],
                   "dosage": "1 tablet 3 times a day after meals",
                   "dosage_ko": "1일 3회 1정 식후 복용"})


def test_a_cold_medicine_box_produces_ordered_warnings():
    card, status = extract_label(
        "성분: 이부프로펜 슈도에페드린 용법 1일 3회 1정 식후 복용", FakeLlm(COLD), RULES)
    assert status == "ok"
    assert card.ingredients_found is True
    assert card.ingredients_ko == ["이부프로펜", "슈도에페드린"]
    assert [w["rule_id"] for w in card.warnings] == ["nsaid", "decongestant"]
    assert card.dosage == "1 tablet 3 times a day after meals"


def test_the_warning_survives_the_model_missing_the_ingredient():
    """Spec §5.2 through the real extraction path, not just the matcher."""
    blind = json.dumps({"product_name": "Unknown box", "kind": "medicine",
                        "ingredients": [], "dosage": ""})
    card, _ = extract_label("성분 이부프로펜 200mg", FakeLlm(blind), RULES)
    assert [w["rule_id"] for w in card.warnings] == ["nsaid"]
    assert card.warnings[0]["found_in"] == ["ocr_text"]


def test_a_warning_carries_every_matched_name_for_her_to_check():
    card, _ = extract_label("성분: 이부프로펜, 아스피린, 나프록센", FakeLlm("{}"), RULES)
    assert set(card.warnings[0]["matched"]) >= {"이부프로펜", "아스피린", "나프록센"}


def test_zero_ingredients_is_a_visible_failure_not_a_clean_card():
    """Spec §3.2."""
    card, _ = extract_label("흐릿한 글자", FakeLlm(json.dumps({"ingredients": []})), RULES)
    assert card.ingredients_found is False
    assert card.product_name == LABEL_ABSENT["product_name"] == "Unidentified product"
    assert card.dosage == LABEL_ABSENT["dosage"] == "Dosage not found — ask the pharmacist"


def test_the_label_prompt_never_asks_the_model_whether_it_is_safe():
    """Spec §5.1."""
    llm = FakeLlm(COLD)
    extract_label("...", llm, RULES)
    p = llm.prompts[0].lower()
    for forbidden in ("safe", "danger", "harmful", "should she", "recommend", "avoid"):
        assert forbidden not in p


def test_a_safe_product_has_no_warnings_but_still_lists_ingredients():
    safe = json.dumps({"product_name": "Tylenol", "kind": "medicine",
                       "ingredients_ko": ["아세트아미노펜"],
                       "ingredients": ["acetaminophen"], "dosage": "1 tablet"})
    card, _ = extract_label("아세트아미노펜 500mg", FakeLlm(safe), RULES)
    assert card.warnings == []
    assert card.ingredients_found is True


def test_a_model_that_returns_nothing_usable_still_screens_the_raw_text():
    """Even with two failed extractions, the box is still screened."""
    card, status = extract_label("성분 이부프로펜 200mg", FakeLlm("junk", "junk"), RULES)
    assert status == "partial"
    assert [w["rule_id"] for w in card.warnings] == ["nsaid"]


def _client(tmp_path, ocr_text, *replies):
    class FakeEngine:
        loaded = False

        def read(self, path):
            return ocr_text

    cfg = load_config(env={"ILGEOJWO_DB": str(tmp_path / "t.db")})
    return TestClient(create_app(cfg, FakeEngine(), FakeLlm(*replies)))


def _png():
    return ("a.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 64), "image/png")


def test_the_label_lens_works_over_http(tmp_path):
    c = _client(tmp_path, "성분: 이부프로펜 200mg 슈도에페드린 30mg", COLD)
    r = c.post("/scan", files={"image": _png()}, data={"lens": "label"})
    body = r.json()
    assert body["status"] == "ok"
    assert [w["rule_id"] for w in body["card"]["warnings"]] == ["nsaid", "decongestant"]


def test_the_document_lens_is_unaffected_by_the_label_branch(tmp_path):
    good_doc = json.dumps({"doc_type": "Notice", "deadline_text": "2026년 10월 5일"})
    c = _client(tmp_path, "출입국관리사무소 체류기간 연장허가 신청 납부기한 2026년 10월 5일 수수료 60,000원", good_doc)
    r = c.post("/scan", files={"image": _png()}, data={"lens": "document"})
    assert r.json()["card"]["deadline"] == "2026-10-05"
    assert "warnings" not in r.json()["card"]


def test_the_page_carries_the_permanent_medical_disclaimer(tmp_path):
    """Spec §5.4 — it must be in the page, not only in a response."""
    page = _client(tmp_path, "x").get("/").text.lower()
    assert "not medical advice" in page
    assert "pharmacist" in page


def test_an_approximate_match_reaches_the_card_flagged_as_approximate(tmp_path):
    """A misread ingredient must still warn her, and must say it is a guess."""
    card, _ = extract_label("성분: 이부프로팬 200mg", FakeLlm("{}"), RULES)
    assert [w["rule_id"] for w in card.warnings] == ["nsaid"]
    assert card.warnings[0]["approximate"] is True


def test_the_page_never_presents_an_empty_warning_list_as_clearance(tmp_path):
    """OCR substitutes syllables and the rule list only covers what is in it, so
    'nothing matched' is not 'this is safe'."""
    page = _client(tmp_path, "x").get("/").text.lower()
    assert "not the same as safe" in page


def test_the_dosage_is_carried_in_korean_too_because_the_model_mistranslated_it():
    """MEASURED on the real stack: EXAONE rendered '1일 3회 1정 식후 복용'
    (one tablet, THREE times a day) as 'Take 1 tablet once daily'. A dosage she
    cannot check against the box is worse than no dosage."""
    reply = json.dumps({"product_name": "ColdES", "kind": "medicine",
                        "ingredients": ["이부프로펜"],
                        "dosage": "Take 1 tablet once daily after meals",
                        "dosage_ko": "1일 3회 1정 식후 복용"})
    card, _ = extract_label("1일 3회 1정 식후 복용", FakeLlm(reply), RULES)
    assert card.dosage_ko == "1일 3회 1정 식후 복용"
    assert card.dosage == "Take 1 tablet once daily after meals"


def test_a_missing_korean_dosage_is_empty_not_invented():
    card, _ = extract_label("흐릿한 글자", FakeLlm("{}"), RULES)
    assert card.dosage_ko == ""


def test_the_label_prompt_asks_for_the_dosage_verbatim_in_korean():
    llm = FakeLlm(COLD)
    extract_label("...", llm, RULES)
    assert "dosage_ko" in llm.prompts[0]


def test_the_page_shows_the_korean_dosage_as_the_checkable_one(tmp_path):
    page = _client(tmp_path, "x").get("/").text
    assert "dosage_ko" in page


def test_ingredients_are_carried_in_korean_and_grounded_in_the_scanned_text():
    reply = json.dumps({"ingredients_ko": ["이부프로편", "수도에페드린염산염"],
                        "ingredients": ["ibuprofen", "cetirizine hydrochloride"]})
    card, _ = extract_label("성분 이부프로편 2OOmg 수도에페드린염산염 3Omg",
                            FakeLlm(reply), RULES)
    assert card.ingredients_ko == ["이부프로편", "수도에페드린염산염"]
    assert card.ingredients_found is True


def test_a_korean_ingredient_the_scan_does_not_contain_is_not_shown_as_fact():
    """MEASURED on the real stack: EXAONE turned 슈도에페드린 (pseudoephedrine)
    into 'cetirizine hydrochloride' — a different drug in a different class — and
    invented 'ketofenilamine maleate'. Model output absent from the scanned text
    must not appear on her card as an ingredient."""
    reply = json.dumps({"ingredients_ko": ["이부프로펜", "세티리진염산염"],
                        "ingredients": ["ibuprofen", "cetirizine hydrochloride"]})
    card, _ = extract_label("성분 이부프로펜 200mg", FakeLlm(reply), RULES)
    assert card.ingredients_ko == ["이부프로펜"]
    assert card.ingredients_unverified == ["세티리진염산염"]


def test_invented_ingredients_cannot_suppress_the_zero_ingredient_notice():
    """Spec §3.2 was bypassed by a model that invents three plausible
    excipients: ingredients_found came from model truthiness, not evidence."""
    reply = json.dumps({"ingredients_ko": ["아스코르브산", "스테아르산마그네슘", "셀룰로스"],
                        "ingredients": ["ascorbic acid", "magnesium stearate"]})
    card, _ = extract_label("흐릿 글자 번짐 반사 광택 포장 알수없음 내용 불명 사진",
                            FakeLlm(reply), RULES)
    assert card.ingredients_found is False
    assert card.ingredients_ko == []


def test_ungrounded_ingredients_are_still_screened_for_risk():
    """Screen generously, display conservatively: a name we will not show her is
    still checked, because over-warning is survivable and under-warning is not."""
    reply = json.dumps({"ingredients_ko": ["이부프로펜"], "ingredients": ["ibuprofen"]})
    card, _ = extract_label("흐릿한 글자 포장 반사 광택 알수없음 내용 불명 사진",
                            FakeLlm(reply), RULES)
    assert [w["rule_id"] for w in card.warnings] == ["nsaid"]
    assert card.ingredients_found is False


def test_a_dosage_the_scan_does_not_contain_is_not_presented_as_verbatim():
    """The page tells her to trust the Korean dosage line. It must therefore be
    a line that is actually on the box."""
    reply = json.dumps({"dosage": "Take 1 tablet", "dosage_ko": "1일 1회 1정 복용"})
    card, _ = extract_label("성분 이부프로펜 200mg 용법 1일 3회", FakeLlm(reply), RULES)
    assert card.dosage_ko == ""


def test_the_label_prompt_asks_for_ingredients_verbatim_in_korean():
    llm = FakeLlm(COLD)
    extract_label("...", llm, RULES)
    assert "ingredients_ko" in llm.prompts[0]


def test_a_short_label_is_still_screened_even_when_judged_unreadable(tmp_path):
    """A blister foil reading exactly '이부프로펜 200mg' is 5 Hangul syllables,
    below min_hangul=10, so the gate calls the scan unreadable. The OCR read it
    perfectly. The NSAID must still be flagged — otherwise the readability gate
    is a silent false negative upstream of the matcher, which is the exact
    failure spec §5.2 exists to prevent."""
    c = _client(tmp_path, "이부프로펜 200mg")
    r = c.post("/scan", files={"image": _png()}, data={"lens": "label"})
    body = r.json()
    assert body["status"] == "unreadable"
    assert [w["rule_id"] for w in body["warnings"]] == ["nsaid"]
    assert "more light" not in body["message"]


def test_an_unreadable_label_with_nothing_found_says_so_plainly(tmp_path):
    c = _client(tmp_path, "")
    r = c.post("/scan", files={"image": _png()}, data={"lens": "label"})
    body = r.json()
    assert body["status"] == "unreadable"
    assert body["warnings"] == []
    assert "more light" in body["message"]


def test_an_unreadable_document_is_not_screened_for_medicine_risk(tmp_path):
    c = _client(tmp_path, "이부프로펜")
    r = c.post("/scan", files={"image": _png()}, data={"lens": "document"})
    assert r.json()["warnings"] == []


def test_an_ingredient_the_ocr_misread_is_still_counted_as_grounded():
    """The golden run caught this: the model returned '이부프로펜 200mg' while the
    OCR had written '이부프로편 2OOmg'. Exact containment rejected a name that is
    genuinely on the box. Grounding has to tolerate the same misreads the fuzzy
    tier exists for — otherwise it manufactures the hallucination it screens for."""
    reply = json.dumps({"ingredients_ko": ["이부프로펜 200mg", "수도에페드린염산염 30mg"],
                        "ingredients": ["ibuprofen", "pseudoephedrine"]})
    card, _ = extract_label("성분 및 함량 이부프로편 2OOmg 수도에페드린염산염 3Omg",
                            FakeLlm(reply), RULES)
    assert card.ingredients_found is True
    assert "이부프로펜 200mg" in card.ingredients_ko


def test_a_different_drug_is_still_rejected_despite_the_tolerance():
    """The tolerance must not be wide enough to admit the measured hallucination."""
    reply = json.dumps({"ingredients_ko": ["세티리진염산염"], "ingredients": ["cetirizine"]})
    card, _ = extract_label("성분 및 함량 이부프로편 2OOmg", FakeLlm(reply), RULES)
    assert card.ingredients_ko == []
    assert card.ingredients_unverified == ["세티리진염산염"]


def test_truncation_never_weakens_the_risk_screening():
    """The model sees a shortened document; the matcher must still see all of it,
    or an ingredient printed late on a long label would stop being screened."""
    buried = "가나다라마바사 " * 900 + " 성분 이부프로펜 200mg"
    card, _ = extract_label(buried, FakeLlm("{}"), RULES)
    assert [w["rule_id"] for w in card.warnings] == ["nsaid"]
