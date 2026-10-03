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
                   "ingredients": ["이부프로펜 200mg", "슈도에페드린 30mg"],
                   "dosage": "1 tablet 3 times a day after meals"})


def test_a_cold_medicine_box_produces_ordered_warnings():
    card, status = extract_label("성분: 이부프로펜 슈도에페드린", FakeLlm(COLD), RULES)
    assert status == "ok"
    assert card.ingredients_found is True
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
                       "ingredients": ["아세트아미노펜 500mg"], "dosage": "1 tablet"})
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
    c = _client(tmp_path, "출입국관리사무소 체류기간 연장허가 신청", good_doc)
    r = c.post("/scan", files={"image": _png()}, data={"lens": "document"})
    assert r.json()["card"]["deadline"] == "2026-10-05"
    assert "warnings" not in r.json()["card"]


def test_the_page_carries_the_permanent_medical_disclaimer(tmp_path):
    """Spec §5.4 — it must be in the page, not only in a response."""
    page = _client(tmp_path, "x").get("/").text.lower()
    assert "not medical advice" in page
    assert "pharmacist" in page
