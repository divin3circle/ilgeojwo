"""The model reads; this decides (spec §5).

Pure functions only. No I/O, no network, no model. It matches against the raw
OCR text as well as the extracted ingredient list, so a model failure can
produce a false positive but not a silent false negative (spec §5.2).

That guarantee is bounded, and the bound is worth stating: it holds for the
ingredient names present in the rule file, mangled by whitespace, line breaks,
hyphenation, invisible characters, full-width Latin or Unicode decomposition. It
does NOT hold for an ingredient the rule file does not list, or for OCR that
substitutes one Hangul syllable for a similar-looking one. See the README.
"""

from __future__ import annotations

from dataclasses import dataclass

from .normalize import normalize
from .rules import Rule

_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}

# A severity the loader somehow let through sorts FIRST, never below "low":
# over-prominence is a survivable failure, burial is not.
_UNKNOWN_SEVERITY_SORTS_FIRST = -1

# Joins list entries so that stripping whitespace cannot fuse two harmless
# fragments into an ingredient name that was never there. No pattern can
# contain it, and normalize() does not remove it.
_SEPARATOR = "\x00"


@dataclass(frozen=True)
class RiskWarning:
    rule_id: str
    severity: str
    message: str
    matched: tuple[str, ...]
    found_in: tuple[str, ...]  # "ingredients", "ocr_text", or both


def _haystack_from_list(values: object) -> str:
    """Never raises. A crash in the safety module means zero warnings."""
    if values is None or isinstance(values, (str, bytes)):
        return normalize(values) if isinstance(values, str) else ""
    try:
        items = list(values)  # type: ignore[call-overload]
    except TypeError:
        return ""
    return normalize(_SEPARATOR.join(v for v in items if isinstance(v, str)))


def _hits(rule: Rule, haystack: str) -> tuple[str, ...]:
    if not haystack:
        return ()
    return tuple(p for p in (*rule.match_ko, *rule.match_en) if normalize(p) in haystack)


def match_risks(ingredients: object, raw_text: object,
                rules: tuple[Rule, ...]) -> list[RiskWarning]:
    from_ingredients = _haystack_from_list(ingredients)
    from_ocr = normalize(raw_text) if isinstance(raw_text, str) else ""

    warnings: list[RiskWarning] = []
    for rule in rules:
        in_ingredients = _hits(rule, from_ingredients)
        in_ocr = _hits(rule, from_ocr)
        if not (in_ingredients or in_ocr):
            continue
        warnings.append(RiskWarning(
            rule_id=rule.id,
            severity=rule.severity,
            message=rule.message_en,
            # dict.fromkeys de-duplicates while keeping rule-file order.
            matched=tuple(dict.fromkeys((*in_ingredients, *in_ocr))),
            found_in=tuple(source for source, hits in
                           (("ingredients", in_ingredients), ("ocr_text", in_ocr)) if hits),
        ))

    return sorted(warnings,
                  key=lambda w: _SEVERITY_ORDER.get(w.severity, _UNKNOWN_SEVERITY_SORTS_FIRST))
