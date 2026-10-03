"""Korean text in, a validated card out. Makes no judgements."""

from __future__ import annotations

import json
import re
from typing import Protocol

from .dates import parse_korean_date
from .prompts import DOCUMENT, DOCUMENT_RETRY
from .schema import ABSENT, DocumentCard

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
