"""Korean text in, a validated card out. Makes no judgements."""

from __future__ import annotations

import json
import re
from typing import Protocol

from ..risk.matcher import match_risks
from ..risk.rules import Rule
from .dates import parse_korean_date
from .prompts import DOCUMENT, DOCUMENT_RETRY, LABEL, LABEL_RETRY
from .schema import ABSENT, LABEL_ABSENT, DocumentCard, LabelCard

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


class LlmClient(Protocol):
    def complete(self, prompt: str) -> str: ...


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


def _to_card(data: dict) -> DocumentCard:
    deadline_text = (data.get("deadline_text") or "").strip()
    return DocumentCard(
        doc_type=(data.get("doc_type") or "").strip() or ABSENT["doc_type"],
        sender=(data.get("sender") or "").strip() or ABSENT["sender"],
        action=(data.get("action") or "").strip() or ABSENT["action"],
        # Parsed from deadline_text alone. issued_text is never consulted, so an
        # issue date cannot leak into the deadline field (Review Focus 1).
        deadline=parse_korean_date(deadline_text),
        deadline_text=deadline_text,
        amount=(data.get("amount") or "").strip() or ABSENT["amount"],
        location=(data.get("location") or "").strip(),
    )


def extract_document(ocr_text: str, llm: LlmClient) -> tuple[DocumentCard, str]:
    for prompt in (DOCUMENT, DOCUMENT_RETRY):
        if (data := _parse_json(llm.complete(prompt.format(text=ocr_text)))) is not None:
            return _to_card(data), "ok"
    return DocumentCard(), "partial"


class ModelUnavailable(RuntimeError):
    """Raised when the local model cannot be reached. Spec §7: name the fix."""


class OllamaClient:
    def __init__(self, url: str, model: str) -> None:
        self._url, self._model = url.rstrip("/"), model

    def complete(self, prompt: str) -> str:
        import urllib.error
        import urllib.request

        body = json.dumps(
            {"model": self._model, "prompt": prompt, "stream": False,
             "options": {"temperature": 0}}
        ).encode()
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


def _to_label_card(data: dict, ocr_text: str, rules: tuple[Rule, ...]) -> LabelCard:
    ingredients = [str(i).strip() for i in (data.get("ingredients") or []) if str(i).strip()]
    # The raw OCR text is passed in regardless of what the model returned, so a
    # model that missed an ingredient cannot suppress its warning (spec §5.2).
    warnings = match_risks(ingredients, ocr_text, rules)
    return LabelCard(
        product_name=(data.get("product_name") or "").strip() or LABEL_ABSENT["product_name"],
        kind=(data.get("kind") or "").strip() or LABEL_ABSENT["kind"],
        ingredients=ingredients,
        dosage=(data.get("dosage") or "").strip() or LABEL_ABSENT["dosage"],
        dosage_ko=(data.get("dosage_ko") or "").strip(),
        warnings=[{"rule_id": w.rule_id, "severity": w.severity,
                   "message": w.message, "matched": list(w.matched),
                   "found_in": list(w.found_in),
                   "approximate": w.approximate} for w in warnings],
        ingredients_found=bool(ingredients),
    )


def extract_label(ocr_text: str, llm: LlmClient,
                  rules: tuple[Rule, ...]) -> tuple[LabelCard, str]:
    for prompt in (LABEL, LABEL_RETRY):
        if (data := _parse_json(llm.complete(prompt.format(text=ocr_text)))) is not None:
            return _to_label_card(data, ocr_text, rules), "ok"
    # Even with no usable model output at all, the box is still screened.
    return _to_label_card({}, ocr_text, rules), "partial"
