import json
from datetime import date

from ilgeojwo.extract.extractor import extract_document
from ilgeojwo.extract.schema import ABSENT, DocumentCard


class FakeLlm:
    """Returns canned replies in order, and records every prompt it saw."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts = []

    def complete(self, prompt):
        self.prompts.append(prompt)
        return self.replies.pop(0) if self.replies else "{}"


GOOD = json.dumps({
    "doc_type": "Residence permit extension notice",
    "sender": "Seoul Immigration Office",
    "action": "Submit the extension application in person with your passport",
    "deadline_text": "2026년 10월 5일",
    "amount": "60,000 KRW",
    "location": "Seoul Immigration Office, 2nd floor",
})


def test_a_clean_reply_becomes_a_complete_card():
    card, status = extract_document("출입국 ...", FakeLlm(GOOD))
    assert status == "ok"
    assert card.doc_type == "Residence permit extension notice"
    assert card.deadline == date(2026, 10, 5)
    assert card.amount == "60,000 KRW"


def test_missing_fields_render_the_exact_absence_strings_from_the_spec():
    card, status = extract_document("...", FakeLlm("{}"))
    assert card.doc_type == ABSENT["doc_type"] == "Unidentified document"
    assert card.sender == ABSENT["sender"] == "Unknown sender"
    assert card.action == ABSENT["action"] == "No clear action found"
    assert card.deadline is None
    assert card.amount == ABSENT["amount"] == "No amount found"


def test_two_dates_never_silently_become_the_wrong_deadline():
    """Review Focus 1. The issue date must not land in the deadline field."""
    reply = json.dumps({
        "doc_type": "Utility bill",
        "deadline_text": "2026년 11월 20일",
        "issued_text": "2026년 10월 1일",
    })
    card, _ = extract_document("발행일 2026년 10월 1일 납부기한 2026년 11월 20일", FakeLlm(reply))
    assert card.deadline == date(2026, 11, 20)


def test_an_unparseable_deadline_is_null_and_the_korean_is_still_shown():
    reply = json.dumps({"doc_type": "Notice", "deadline_text": "곧"})
    card, _ = extract_document("곧 처리하세요", FakeLlm(reply))
    assert card.deadline is None
    assert card.deadline_text == "곧"


def test_invalid_json_is_retried_once_with_a_stricter_prompt():
    llm = FakeLlm("I think this is a bill about water.", GOOD)
    card, status = extract_document("...", llm)
    assert status == "ok"
    assert len(llm.prompts) == 2
    assert "JSON" in llm.prompts[1]


def test_two_failures_degrade_to_partial_rather_than_inventing_a_card():
    llm = FakeLlm("nope", "still nope")
    card, status = extract_document("...", llm)
    assert status == "partial"
    assert card.doc_type == ABSENT["doc_type"]
    assert card.deadline is None


def test_json_wrapped_in_a_markdown_fence_is_still_accepted():
    card, status = extract_document("...", FakeLlm(f"```json\n{GOOD}\n```"))
    assert status == "ok"
    assert card.sender == "Seoul Immigration Office"


def test_a_stopped_ollama_gives_a_clear_setup_error_naming_the_fix():
    """Spec §7: a missing model must name the component and the command.
    Port 1 refuses instantly, so this needs no network."""
    import pytest

    from ilgeojwo.extract.extractor import ModelUnavailable, OllamaClient
    with pytest.raises(ModelUnavailable) as e:
        OllamaClient("http://127.0.0.1:1", "exaone3.5:2.4b").complete("hi")
    assert "ollama serve" in str(e.value)
    assert "exaone3.5:2.4b" in str(e.value)


def test_the_extraction_prompt_never_asks_the_model_for_a_judgement():
    """Spec §5.1: the model reads. It does not decide."""
    llm = FakeLlm(GOOD)
    extract_document("...", llm)
    p = llm.prompts[0].lower()
    for forbidden in ("safe", "danger", "should she", "recommend", "advise"):
        assert forbidden not in p
