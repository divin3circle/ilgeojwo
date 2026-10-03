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
    card, status = extract_document("출입국관리사무소 체류기간 연장허가 신청 납부기한 2026년 10월 5일 수수료 60,000원", FakeLlm(GOOD))
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


def test_an_issue_date_landing_in_the_deadline_field_yields_no_deadline():
    """Review Focus 1's only real defence was prompt wording, from a model this
    branch measured turning 'three times a day' into 'once daily'. If the two
    dates come back identical, the deadline is not known."""
    reply = json.dumps({"doc_type": "Utility bill",
                        "deadline_text": "2026년 10월 1일",
                        "issued_text": "2026년 10월 1일"})
    card, _ = extract_document("발행일 2026년 10월 1일", FakeLlm(reply))
    assert card.deadline is None
    assert card.deadline_text == "2026년 10월 1일"


def test_a_deadline_the_scan_does_not_contain_is_not_treated_as_printed():
    """A model that reads 10월 5일까지 and helpfully supplies the year has
    invented a deadline, which the Global Constraint forbids."""
    reply = json.dumps({"doc_type": "Notice", "deadline_text": "2026년 10월 5일"})
    card, _ = extract_document("납부기한 10월 5일까지", FakeLlm(reply))
    assert card.deadline is None


KOREAN_REPLY = json.dumps({
    "doc_type": "항공권 발행 확인서",
    "sender": "(주)클럽가이아",
    "action": "본 전자항공권 발행확인서를 통해 탑승수속, 입출국, 세관 통과 시 요구되므로 전 여행기간 동안 소지하시기 바랍니다.",
    "amount": "KRW 212,400",
})
ENGLISH_REPLY = json.dumps({
    "doc_type": "E-ticket confirmation",
    "sender": "Club Gaia Co., Ltd.",
    "action": "Carry this document for the whole trip — it is required at check-in, immigration and customs.",
    "amount": "KRW 212,400",
})


def test_korean_left_in_an_english_field_is_retried_as_a_translation():
    """A real e-ticket came back with doc_type '항공권 발행 확인서' and an entirely
    Korean action paragraph. She cannot read Korean — that is the whole point —
    so an untranslated field is a failed extraction, not a result."""
    llm = FakeLlm(KOREAN_REPLY, ENGLISH_REPLY)
    card, status = extract_document("항공권 발행 확인서 ...", llm)
    assert card.doc_type == "E-ticket confirmation"
    assert card.sender == "Club Gaia Co., Ltd."
    assert status == "ok"
    assert len(llm.prompts) == 2
    assert "English" in llm.prompts[1]


def test_a_model_that_will_not_translate_says_so_rather_than_pretending():
    card, status = extract_document("...", FakeLlm(KOREAN_REPLY, KOREAN_REPLY))
    assert card.untranslated is True
    assert card.doc_type == "항공권 발행 확인서"


def test_a_translated_card_is_not_marked_untranslated():
    card, _ = extract_document("...", FakeLlm(ENGLISH_REPLY))
    assert card.untranslated is False


def test_the_korean_deadline_text_is_not_mistaken_for_a_failed_translation():
    """deadline_text is deliberately verbatim Korean and must not trigger a retry."""
    reply = json.dumps({"doc_type": "Utility bill", "sender": "KEPCO",
                        "action": "Pay the balance.", "deadline_text": "2026년 10월 5일"})
    llm = FakeLlm(reply)
    card, _ = extract_document("납부기한 2026년 10월 5일", llm)
    assert card.untranslated is False
    assert len(llm.prompts) == 1


def test_a_very_long_document_is_shortened_before_the_model_sees_it():
    """A 6-page e-ticket produced 10,035 characters of OCR. The model failed to
    return usable JSON twice and the card came back empty after 256 seconds.
    Pages 2-8 were terms and conditions drowning the signal on page 1."""
    from ilgeojwo.extract.extractor import MAX_EXTRACT_CHARS
    long_document = "출입국관리사무소 체류기간 연장허가 신청 " * 800
    llm = FakeLlm(GOOD)
    extract_document(long_document, llm)
    # Measure the document, not the prompt template around it.
    assert "rest of the document not shown" in llm.prompts[0]
    assert len(llm.prompts[0]) < len(long_document) / 2
    assert MAX_EXTRACT_CHARS < len(long_document)


def test_a_short_document_is_passed_whole():
    llm = FakeLlm(GOOD)
    short = "출입국관리사무소 납부기한 2026년 10월 5일"
    extract_document(short, llm)
    assert short in llm.prompts[0]


TRANSLATED = json.dumps({
    "doc_type": "E-ticket confirmation",
    "sender": "Club Gaia Co., Ltd.",
    "action": "Carry this document for the whole trip.",
})


def test_a_card_left_in_korean_gets_a_focused_translation_pass():
    """Measured: on a real e-ticket the 2.4B model returned Korean twice, even
    when the retry said why. Re-doing the whole extraction is a hard task for a
    small model; translating three strings is not."""
    llm = FakeLlm(KOREAN_REPLY, KOREAN_REPLY, TRANSLATED)
    card, status = extract_document("항공권 ...", llm)
    assert card.doc_type == "E-ticket confirmation"
    assert card.sender == "Club Gaia Co., Ltd."
    assert card.untranslated is False
    assert len(llm.prompts) == 3
    assert "Translate" in llm.prompts[2]


def test_the_translation_pass_keeps_the_fields_it_cannot_improve():
    partial = json.dumps({"doc_type": "E-ticket confirmation"})
    llm = FakeLlm(KOREAN_REPLY, KOREAN_REPLY, partial)
    card, _ = extract_document("...", llm)
    assert card.doc_type == "E-ticket confirmation"
    assert card.untranslated is True   # sender and action are still Korean


def test_when_even_the_translation_pass_fails_the_card_says_so():
    llm = FakeLlm(KOREAN_REPLY, KOREAN_REPLY, KOREAN_REPLY)
    card, _ = extract_document("...", llm)
    assert card.untranslated is True
    assert len(llm.prompts) == 3


def test_the_amount_and_deadline_survive_the_translation_pass():
    llm = FakeLlm(KOREAN_REPLY, KOREAN_REPLY, TRANSLATED)
    card, _ = extract_document("총액 KRW 212,400", llm)
    assert card.amount == "KRW 212,400"


def test_the_prompt_describes_the_shape_the_scan_actually_arrives_in():
    """Measured on a real e-ticket: the OCR returns one box per line, so a Korean
    multi-column table arrives as a flat list with every label on its own line,
    separated from its value. The model picked the staff member under 담당자 as
    the sender, and translated the label 발행 as the action."""
    llm = FakeLlm(ENGLISH_REPLY)
    extract_document("...", llm)
    prompt = llm.prompts[0]
    assert "one line at a time" in prompt
    assert "label" in prompt.lower()


def test_the_prompt_says_what_a_sender_is_and_what_an_action_is():
    llm = FakeLlm(ENGLISH_REPLY)
    extract_document("...", llm)
    prompt = llm.prompts[0]
    assert "issued" in prompt.lower()
    assert "No action needed" in prompt


def test_an_informational_document_may_legitimately_have_no_action():
    reply = json.dumps({"doc_type": "E-ticket confirmation", "sender": "Club Gaia",
                        "action": "No action needed", "amount": "KRW 212,400"})
    card, _ = extract_document("항공권", FakeLlm(reply))
    assert card.action == "No action needed"
    assert card.untranslated is False
