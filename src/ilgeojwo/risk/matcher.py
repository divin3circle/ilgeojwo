"""The model reads; this decides (spec §5).

Pure functions only. No I/O, no network, no model. It matches against the raw
OCR text as well as the extracted ingredient list, so a model failure can
produce a false positive but not a silent false negative (spec §5.2).

That guarantee is bounded, and the bound is worth stating: it holds for the
ingredient names present in the rule file, mangled by whitespace, line breaks,
hyphenation, invisible characters, full-width Latin or Unicode decomposition, or
a single substituted character in a name of at least four. It does NOT hold for
an ingredient the rule file does not list, nor for two or more substitutions, nor
for a short name misread. See the README.

The single-substitution tier exists because of a measurement, not a hunch: on a
clean rendered Korean document EasyOCR returned 연장히가 for 연장허가, 신청서클
for 신청서를, and 남부금액 for 납부금액. Three substitutions on easy input. An
exact-only matcher would silently drop the warning for a box that really does
contain the ingredient.
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

# Default floor only. Below this length a single changed character is usually too
# weak a signal. But length alone is the wrong discriminator — 이산화황 sits one
# substitution from 이산화티타늄/이산화탄소/이산화규소, which are on a large share
# of Korean tablets and drinks, while 코데인 is short AND high-severity AND fragile
# to the commonest Korean misread (ㅔ/ㅐ). So each rule may override per pattern
# via no_fuzzy / force_fuzzy, and the decision is reviewable in the rule file.
_MIN_FUZZY_LENGTH = 4


@dataclass(frozen=True)
class RiskWarning:
    rule_id: str
    severity: str
    message: str
    matched: tuple[str, ...]
    found_in: tuple[str, ...]  # "ingredients", "ocr_text", or both
    approximate: bool = False  # matched one substitution away, not exactly


def _haystack_from_list(values: object) -> str:
    """Never raises. A crash in the safety module means zero warnings."""
    if values is None or isinstance(values, (str, bytes)):
        return normalize(values) if isinstance(values, str) else ""
    try:
        items = list(values)  # type: ignore[call-overload]
    except TypeError:
        return ""
    return normalize(_SEPARATOR.join(v for v in items if isinstance(v, str)))


def _patterns(rule: Rule) -> tuple[str, ...]:
    return (*rule.match_ko, *rule.match_en)


def _hits(rule: Rule, haystack: str) -> tuple[str, ...]:
    if not haystack:
        return ()
    return tuple(p for p in _patterns(rule) if normalize(p) in haystack)


def _one_substitution_away(needle: str, haystack: str) -> bool:
    """True if haystack holds a same-length window differing in exactly one char."""
    size = len(needle)
    for start in range(len(haystack) - size + 1):
        window = haystack[start:start + size]
        if _SEPARATOR in window:
            # A window straddling two list entries is not one ingredient name.
            # Without this, ["에", "페드린"] matches 에페드린 one substitution away.
            continue
        differences = 0
        for a, b in zip(needle, window):
            if a != b:
                differences += 1
                if differences > 1:
                    break
        else:
            if differences == 1:
                return True
    return False


def _fuzzy_eligible(rule: Rule, pattern: str) -> bool:
    if pattern in rule.force_fuzzy:
        return True
    if pattern in rule.no_fuzzy:
        return False
    return len(normalize(pattern)) >= _MIN_FUZZY_LENGTH


def _approximate_hits(rule: Rule, haystack: str) -> tuple[str, ...]:
    if not haystack:
        return ()
    found = []
    for pattern in _patterns(rule):
        if _fuzzy_eligible(rule, pattern) and _one_substitution_away(
                normalize(pattern), haystack):
            found.append(pattern)
    return tuple(found)


def match_risks(ingredients: object, raw_text: object,
                rules: tuple[Rule, ...]) -> list[RiskWarning]:
    from_ingredients = _haystack_from_list(ingredients)
    from_ocr = normalize(raw_text) if isinstance(raw_text, str) else ""

    warnings: list[RiskWarning] = []
    for rule in rules:
        in_ingredients = _hits(rule, from_ingredients)
        in_ocr = _hits(rule, from_ocr)
        approximate = False

        if not (in_ingredients or in_ocr):
            # Only when nothing matched exactly, so a clean hit is never
            # downgraded to a guess.
            in_ingredients = _approximate_hits(rule, from_ingredients)
            in_ocr = _approximate_hits(rule, from_ocr)
            if not (in_ingredients or in_ocr):
                continue
            approximate = True

        warnings.append(RiskWarning(
            rule_id=rule.id,
            severity=rule.severity,
            message=rule.message_en,
            # dict.fromkeys de-duplicates while keeping rule-file order.
            matched=tuple(dict.fromkeys((*in_ingredients, *in_ocr))),
            found_in=tuple(source for source, hits in
                           (("ingredients", in_ingredients), ("ocr_text", in_ocr)) if hits),
            approximate=approximate,
        ))

    return sorted(warnings,
                  key=lambda w: _SEVERITY_ORDER.get(w.severity, _UNKNOWN_SEVERITY_SORTS_FIRST))
