"""Korean text in, a validated card out. Makes no judgements."""

from __future__ import annotations

import json
import re
from typing import Protocol

from ..ocr.reader import PAGE_BREAK
from ..risk.matcher import match_risks
from ..risk.normalize import normalize
from ..risk.rules import Rule
from .dates import parse_korean_date
from .prompts import DOCUMENT, DOCUMENT_RETRY, LABEL, LABEL_RETRY, TRANSLATE
from .schema import ABSENT, LABEL_ABSENT, DocumentCard, LabelCard

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
_HANGUL = re.compile(r"[\uac00-\ud7a3]")

# Fields the reader must be able to read. deadline_text and issued_text are
# deliberately verbatim Korean and are excluded.
_MUST_BE_ENGLISH = ("doc_type", "sender", "action")

# How much scanned text the model is shown. A 6-page e-ticket yielded 10,035
# characters and the 2.4B model returned nothing usable from it, twice, in four
# minutes. Korean official documents put the identifying information and the
# deadline at the top; the rest is terms and conditions. The matcher is NEVER
# given the shortened text — it always screens everything.
MAX_EXTRACT_CHARS = 3500


def _for_model(ocr_text: str) -> str:
    """Page one, capped.

    Measured: the same page read alone gave the right sender; read as page one of
    eight it gave 'Issuer'. Truncating a concatenation mid-document was worse than
    taking the page that actually carries the identifying information.
    """
    first = ocr_text.split(PAGE_BREAK)[0]
    if len(first) <= MAX_EXTRACT_CHARS:
        return first
    return first[:MAX_EXTRACT_CHARS] + "\n[... rest of the page not shown ...]"


def _still_korean(data: dict) -> bool:
    return any(_HANGUL.search(str(data.get(field) or "")) for field in _MUST_BE_ENGLISH)


class LlmClient(Protocol):
    def complete(self, prompt: str, schema: dict | None = None) -> str: ...


# Ollama constrains generation to this shape, which removes two failure classes
# outright: unparseable replies, and invented or missing keys. Measured: asked one
# focused question under a schema the 2.4B returned the correct issuer, where the
# same model given eight fields in prose returned the translation of a heading.
_STR = {"type": "string"}
DOCUMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "doc_type": _STR, "sender": _STR, "action": _STR,
        "deadline_text": _STR, "issued_text": _STR, "amount": _STR, "location": _STR,
        "details": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"label": _STR, "value": _STR},
                "required": ["label", "value"],
            },
        },
    },
    "required": ["doc_type", "sender", "action", "deadline_text", "amount"],
}

LABEL_SCHEMA = {
    "type": "object",
    "properties": {
        "product_name": _STR, "kind": _STR,
        "ingredients_ko": {"type": "array", "items": _STR},
        "ingredients": {"type": "array", "items": _STR},
        "dosage": _STR, "dosage_ko": _STR,
    },
    "required": ["product_name", "ingredients_ko", "ingredients"],
}


def _ask(llm: LlmClient, prompt: str, schema: dict | None) -> str:
    """Older clients and test fakes may not take a schema."""
    try:
        return llm.complete(prompt, schema)
    except TypeError:
        return llm.complete(prompt)


def _parse_json(reply: str) -> dict | None:
    candidate = reply.strip()
    if m := _FENCE.search(candidate):
        candidate = m.group(1)
    if (start := candidate.find("{")) != -1 and (end := candidate.rfind("}")) != -1:
        candidate = candidate[start : end + 1]
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


# An instruction is a sentence. The model returned "Issuance" — its translation
# of the Korean label 발행 — which tells her nothing she can act on.
_REAL_ANSWERS = {"no action needed"}

# Words that are field headings on Korean forms, not values. The model printed
# "Issuance" as the action and "Issuer" as the sender, both translations of
# labels (발행, 발행처) while the real answers sat elsewhere on the page.
_LABELS_NOT_VALUES = {
    "issuer", "sender", "issue", "issuance", "issued", "recipient", "applicant",
    "name", "document", "date", "amount", "total", "place", "from", "to",
    "발행", "발행처", "발행일", "담당자", "수신", "발신",
}


def _is_a_value(text: str) -> bool:
    cleaned = text.strip().strip(":：").strip()
    if not cleaned or len(cleaned) < 3:
        return False
    return cleaned.lower() not in _LABELS_NOT_VALUES


def _details_from(value: object) -> list[dict]:
    """Keeps only well-formed, English label/value pairs. Never raises."""
    if not isinstance(value, list):
        return []
    kept = []
    for item in value[:5]:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        text = str(item.get("value") or "").strip()
        if not label or not text:
            continue
        if _HANGUL.search(label) or _HANGUL.search(text):
            continue
        kept.append({"label": label, "value": text})
    return kept


def _is_an_instruction(action: str) -> bool:
    cleaned = action.strip().rstrip(".")
    if cleaned.lower() in _REAL_ANSWERS:
        return True
    return len(cleaned.split()) >= 3


def _to_card(data: dict, ocr_text: str = "") -> DocumentCard:
    deadline_text = (data.get("deadline_text") or "").strip()
    issued_text = (data.get("issued_text") or "").strip()
    deadline = parse_korean_date(deadline_text)

    # The model is not trusted to have copied from the box. If the deadline it
    # reports is not in the scanned text, it was composed, not read.
    if deadline is not None and ocr_text and not _is_in(deadline_text, normalize(ocr_text)):
        deadline, deadline_text = None, deadline_text

    # If the two dates are identical the model almost certainly put the issue
    # date in the deadline field, which Review Focus 1 forbids.
    if deadline is not None and deadline == parse_korean_date(issued_text):
        deadline = None

    return DocumentCard(
        doc_type=(data.get("doc_type") or "").strip() or ABSENT["doc_type"],
        sender=(sender if _is_a_value(sender := (data.get("sender") or "").strip())
                else ABSENT["sender"]),
        action=(action if _is_an_instruction(action := (data.get("action") or "").strip())
                else ABSENT["action"]),
        deadline=deadline,
        deadline_text=deadline_text,
        amount=(data.get("amount") or "").strip() or ABSENT["amount"],
        location=(data.get("location") or "").strip(),
        details=_details_from(data.get("details")),
    )


def extract_document(ocr_text: str, llm: LlmClient) -> tuple[DocumentCard, str]:
    last: dict | None = None
    for prompt in (DOCUMENT, DOCUMENT_RETRY):
        data = _parse_json(_ask(llm, prompt.format(text=_for_model(ocr_text)),
                                DOCUMENT_SCHEMA))
        if data is None:
            continue
        last = data
        if not _still_korean(data):
            return _to_card(data, ocr_text), "ok"
        # Korean in an English field is a failed read, not a result: retry once
        # with a prompt that says so.
    if last is None:
        return DocumentCard(), "partial"

    # Last resort: stop asking it to extract, and ask it only to translate. A
    # narrow task succeeds where the full one does not.
    translated = _parse_json(_ask(llm, TRANSLATE.format(
        doc_type=last.get("doc_type") or "", sender=last.get("sender") or "",
        action=last.get("action") or ""),
        {"type": "object",
         "properties": {"doc_type": _STR, "sender": _STR, "action": _STR},
         "required": ["doc_type", "sender", "action"]}))
    if isinstance(translated, dict):
        merged = dict(last)
        for field in _MUST_BE_ENGLISH:
            value = str(translated.get(field) or "").strip()
            if value and not _HANGUL.search(value):
                merged[field] = value
        last = merged

    card = _to_card(last, ocr_text)
    return card.model_copy(update={"untranslated": _still_korean(last)}), "ok"


class ModelUnavailable(RuntimeError):
    """Raised when the local model cannot be reached. Spec §7: name the fix."""


class OllamaClient:
    def __init__(self, url: str, model: str) -> None:
        self._url, self._model = url.rstrip("/"), model

    def complete(self, prompt: str, schema: dict | None = None) -> str:
        import urllib.error
        import urllib.request

        payload = {"model": self._model, "prompt": prompt, "stream": False,
                   "options": {"temperature": 0}}
        if schema is not None:
            payload["format"] = schema
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{self._url}/api/generate", body, {"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.loads(resp.read())["response"]
        except urllib.error.URLError as exc:
            raise ModelUnavailable(
                f"Could not reach the language model {self._model!r} at {self._url}.\n"
                f"  Start the server with:   ollama serve\n"
                f"  Install the model with:  ollama pull {self._model}"
            ) from exc
        except (TimeoutError, OSError, KeyError, json.JSONDecodeError) as exc:
            # A read timeout is TimeoutError, not URLError. This is the failure a
            # slower laptop meets first, so it must name the way out.
            raise ModelUnavailable(
                f"The language model {self._model!r} did not answer in time "
                f"({type(exc).__name__}).\n"
                f"  On a slower laptop, switch to the smaller model:\n"
                f"    ILGEOJWO_LLM_MODEL=joonoh/HyperCLOVAX-SEED-Text-Instruct-1.5B make run"
            ) from exc


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()]


def _is_in(claim: str, haystack: str) -> bool:
    """Whitespace-insensitive containment, using the matcher's normalisation.

    Used for the deadline and the dosage, where strictness is the safe direction:
    a rejected value shows "not found" rather than a wrong date or frequency.
    """
    needle = normalize(claim)
    return bool(needle) and needle in haystack


# An ingredient name has to survive the OCR substitutions the fuzzy tier exists
# for — 이부프로펜 arriving as 이부프로편, 200 as 2OO. Requiring exact containment
# rejected names genuinely on the box, which manufactured the very hallucination
# the grounding screens for. A hallucination shares almost nothing with the scan;
# a misread shares most of it.
_RESEMBLANCE_FLOOR = 0.6


def _resembles(claim: str, haystack: str, floor: float = _RESEMBLANCE_FLOOR) -> bool:
    needle = normalize(claim)
    if not needle or not haystack:
        return False
    if needle in haystack:
        return True
    from difflib import SequenceMatcher

    matcher = SequenceMatcher(None, needle, haystack, autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    return matched / len(needle) >= floor


def _to_label_card(data: dict, ocr_text: str, rules: tuple[Rule, ...]) -> LabelCard:
    scanned = normalize(ocr_text)
    claimed_ko = _strings(data.get("ingredients_ko"))
    english = _strings(data.get("ingredients"))

    # Grounding: only Korean the scan actually contains may be shown to her as an
    # ingredient. Everything the model said is still screened for risk, because
    # over-warning is survivable and under-warning is not.
    grounded = [name for name in claimed_ko if _resembles(name, scanned)]
    unverified = [name for name in claimed_ko if not _resembles(name, scanned)]

    # The raw OCR text is passed in regardless of what the model returned, so a
    # model that missed an ingredient cannot suppress its warning (spec §5.2).
    warnings = match_risks(claimed_ko + english, ocr_text, rules)

    dosage_ko = (data.get("dosage_ko") or "").strip()
    return LabelCard(
        product_name=(data.get("product_name") or "").strip() or LABEL_ABSENT["product_name"],
        kind=(data.get("kind") or "").strip() or LABEL_ABSENT["kind"],
        ingredients_ko=grounded,
        ingredients_unverified=unverified,
        ingredients=english,
        dosage=(data.get("dosage") or "").strip() or LABEL_ABSENT["dosage"],
        # The page tells her to trust this line, so it must be a line that is
        # actually on the box.
        dosage_ko=dosage_ko if _is_in(dosage_ko, scanned) else "",
        warnings=[{"rule_id": w.rule_id, "severity": w.severity,
                   "message": w.message, "matched": list(w.matched),
                   "found_in": list(w.found_in),
                   "approximate": w.approximate} for w in warnings],
        # From evidence in the image, never from the model having said something.
        ingredients_found=bool(grounded),
    )


def extract_label(ocr_text: str, llm: LlmClient,
                  rules: tuple[Rule, ...]) -> tuple[LabelCard, str]:
    for prompt in (LABEL, LABEL_RETRY):
        reply = _ask(llm, prompt.format(text=_for_model(ocr_text)), LABEL_SCHEMA)
        if (data := _parse_json(reply)) is not None:
            # Full text, not the shortened one: screening never gets less input.
            return _to_label_card(data, ocr_text, rules), "ok"
    # Even with no usable model output at all, the box is still screened.
    return _to_label_card({}, ocr_text, rules), "partial"
