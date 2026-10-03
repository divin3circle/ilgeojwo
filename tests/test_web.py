import io
import json

from fastapi.testclient import TestClient

from ilgeojwo.config import load_config
from ilgeojwo.web.app import create_app

GOOD = json.dumps({
    "doc_type": "Residence permit extension notice",
    "sender": "Seoul Immigration Office",
    "action": "Submit the extension application in person",
    "deadline_text": "2026년 10월 5일", "amount": "60,000 KRW", "location": "",
})


class FakeEngine:
    def __init__(self, text):
        self.text = text

    def read(self, path):
        return self.text


class FakeLlm:
    def __init__(self, *replies):
        self.replies = list(replies)

    def complete(self, prompt):
        return self.replies.pop(0) if self.replies else "{}"


def _client(tmp_path, ocr_text, *llm_replies):
    cfg = load_config(env={"ILGEOJWO_DB": str(tmp_path / "t.db")})
    return TestClient(create_app(cfg, FakeEngine(ocr_text), FakeLlm(*llm_replies)))


def _png():
    return ("a.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 64), "image/png")


def test_the_page_loads(tmp_path):
    r = _client(tmp_path, "출입국관리사무소 체류기간 연장허가").get("/")
    assert r.status_code == 200
    assert "읽어줘" in r.text


def test_uploading_a_korean_document_returns_a_card(tmp_path):
    c = _client(tmp_path, "출입국관리사무소 체류기간 연장허가 신청 납부기한 2026년 10월 5일 수수료 60,000원", GOOD)
    r = c.post("/scan", files={"image": _png()}, data={"lens": "document"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["card"]["deadline"] == "2026-10-05"
    assert body["card"]["sender"] == "Seoul Immigration Office"


def test_the_verbatim_korean_is_always_returned(tmp_path):
    raw = "출입국관리사무소 체류기간 연장허가 신청 납부 60,000원"
    c = _client(tmp_path, raw, GOOD)
    r = c.post("/scan", files={"image": _png()}, data={"lens": "document"})
    assert r.json()["ocr_text"] == raw


def test_an_unreadable_photo_is_reported_not_guessed_at(tmp_path):
    c = _client(tmp_path, "")
    r = c.post("/scan", files={"image": _png()}, data={"lens": "document"})
    assert r.json()["status"] == "unreadable"
    assert "Couldn't read this" in r.json()["message"]
    assert r.json()["card"] is None


def test_an_unreadable_photo_never_calls_the_model(tmp_path):
    """No point asking a model to interpret noise, and it must not be given a chance."""
    cfg = load_config(env={"ILGEOJWO_DB": str(tmp_path / "t.db")})
    llm = FakeLlm()
    calls = []
    llm.complete = lambda p: calls.append(p) or "{}"
    c = TestClient(create_app(cfg, FakeEngine(""), llm))
    c.post("/scan", files={"image": _png()}, data={"lens": "document"})
    assert calls == []


def test_scans_are_persisted_and_listed(tmp_path):
    c = _client(tmp_path, "출입국관리사무소 체류기간 연장허가 신청", GOOD)
    c.post("/scan", files={"image": _png()}, data={"lens": "document"})
    rows = c.get("/scans").json()
    assert len(rows) == 1
    assert rows[0]["lens"] == "document"


def test_a_stopped_model_gives_a_clear_message_not_an_opaque_500(tmp_path):
    """Spec §7, through the web layer. She must be told what to restart."""
    from ilgeojwo.extract.extractor import ModelUnavailable

    class DeadLlm:
        def complete(self, prompt):
            raise ModelUnavailable("Start the server with:   ollama serve")

    cfg = load_config(env={"ILGEOJWO_DB": str(tmp_path / "t.db")})
    c = TestClient(
        create_app(cfg, FakeEngine("출입국관리사무소 체류기간 연장허가 신청"), DeadLlm()),
        raise_server_exceptions=False,
    )
    r = c.post("/scan", files={"image": _png()}, data={"lens": "document"})
    assert r.status_code == 503
    assert "ollama serve" in r.json()["detail"]


def test_an_unknown_lens_is_rejected(tmp_path):
    c = _client(tmp_path, "출입국관리사무소 체류기간 연장허가")
    r = c.post("/scan", files={"image": _png()}, data={"lens": "nonsense"})
    assert r.status_code == 422


def test_the_page_shows_the_deadline_as_printed_in_korean(tmp_path):
    """dates.py claims 'the verbatim Korean text is always shown to the user'.
    A notice reading 10월 5일까지 stores null — correctly — and she was shown only
    'By: No date found' while deadline_text sat unrendered in the card."""
    page = _client(tmp_path, "x").get("/").text
    assert "deadline_text" in page


def test_the_page_lists_saved_scans_by_deadline(tmp_path):
    """Spec §3.1: cards are saved and listed, soonest deadline first. The sorting
    and the DB were correct and unreachable — /scans returned raw JSON that the
    page never fetched."""
    page = _client(tmp_path, "x").get("/").text
    assert "/scans" in page


def test_the_page_offers_the_camera_as_its_own_obvious_choice(tmp_path):
    """On a phone the page said 'Point your camera at it' and then showed a
    button labelled 'Choose File'. The camera was one tap further in, behind an
    OS sheet, and nothing on screen said so."""
    page = _client(tmp_path, "x").get("/").text
    assert 'capture="environment"' in page
    assert "Take a photo" in page
    assert "Choose a file" in page


def test_the_page_tells_her_when_a_card_could_not_be_translated(tmp_path):
    page = _client(tmp_path, "x").get("/").text
    assert "untranslated" in page
    assert "could not be translated" in page.lower()
