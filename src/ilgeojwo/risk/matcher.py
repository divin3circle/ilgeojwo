"""The model reads; this decides (spec §5).

Pure functions only. No I/O, no network, no model. It matches against the raw
OCR text as well as the extracted ingredient list, so a model failure can
produce a false positive but never a silent false negative (spec §5.2).
"""

from __future__ import annotations

from dataclasses import dataclass

from .normalize import normalize
from .rules import Rule

_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


@dataclass(frozen=True)
class RiskWarning:
    rule_id: str
    severity: str
    message: str
    matched: str
    found_in: str  # "ingredients" or "ocr_text"


def _find(rule: Rule, haystack: str) -> str | None:
    for pattern in (*rule.match_ko, *rule.match_en):
        if pattern and normalize(pattern) in haystack:
            return pattern
    return None


def match_risks(ingredients: list[str], raw_text: str,
                rules: tuple[Rule, ...]) -> list[RiskWarning]:
    from_ingredients = normalize(" ".join(ingredients))
    from_ocr = normalize(raw_text)

    warnings: list[RiskWarning] = []
    for rule in rules:
        # Ingredients are checked first only so the message can say where it was
        # seen. Either source alone is enough to raise the warning.
        if (hit := _find(rule, from_ingredients)) is not None:
            source = "ingredients"
        elif (hit := _find(rule, from_ocr)) is not None:
            source = "ocr_text"
        else:
            continue
        warnings.append(RiskWarning(rule.id, rule.severity, rule.message_en, hit, source))

    return sorted(warnings, key=lambda w: _SEVERITY_ORDER.get(w.severity, 99))
