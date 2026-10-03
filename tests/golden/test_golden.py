"""Real images through the real models. Facts are pinned; wording may vary.

Comparison rule (spec §8): exact on deadline, amount and the set of warning ids;
case- and whitespace-insensitive substring match on free-text fields. Free text
may vary in wording; the facts may not.

Fixtures come in two kinds. `*.synthetic.png` are rendered Korean documents,
committed so the suite runs for anyone who clones the repo. `*.private.*` are her
real photos, gitignored, because an immigration letter carries her name, address
and ARC number even with the passport number covered. Only the private ones say
anything about robustness on real phone photos.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ilgeojwo.config import load_config
from ilgeojwo.extract.extractor import OllamaClient, extract_document, extract_label
from ilgeojwo.ocr.reader import build_ocr_engine, read_korean
from ilgeojwo.risk.rules import load_rules

FIXTURES = Path(__file__).parent / "fixtures"
EXPECTED = Path(__file__).parent / "expected"
CASES = sorted(p.stem for p in EXPECTED.glob("*.json"))


def _loose(needle: str, haystack: str) -> bool:
    return "".join(needle.lower().split()) in "".join(haystack.lower().split())


@pytest.fixture(scope="module")
def stack():
    cfg = load_config()
    return (cfg, build_ocr_engine(cfg),
            OllamaClient(cfg.ollama_url, cfg.llm_model), load_rules(cfg.rules_path))


def _image_for(name: str) -> Path:
    matches = [p for p in FIXTURES.glob(f"{name}.*") if p.suffix.lower() != ".json"]
    if not matches:
        pytest.skip(f"no fixture image for {name} (private fixtures are gitignored)")
    return matches[0]


@pytest.mark.slow
@pytest.mark.parametrize("name", CASES)
def test_real_image_extraction(name, stack):
    cfg, engine, llm, rules = stack
    want = json.loads((EXPECTED / f"{name}.json").read_text(encoding="utf-8"))
    ocr = read_korean(_image_for(name), engine, cfg.min_hangul)

    assert ocr.readable is want["readable"], (
        f"{name}: readability mismatch; OCR returned {ocr.text!r}")
    if not want["readable"]:
        return

    if want["lens"] == "document":
        card, _ = extract_document(ocr.text, llm)
        assert str(card.deadline) == str(want["deadline"]), f"{name}: deadline"
        if want.get("amount"):
            assert _loose(want["amount"], card.amount), f"{name}: amount"
        for phrase in want.get("action_contains", []):
            assert _loose(phrase, card.action), f"{name}: action missing {phrase!r}"
    else:
        card, _ = extract_label(ocr.text, llm, rules)
        assert card.ingredients_found is want["ingredients_found"], f"{name}: ingredients"
        assert {w["rule_id"] for w in card.warnings} == set(want["warning_ids"]), (
            f"{name}: warnings")


@pytest.mark.slow
@pytest.mark.parametrize("name", CASES)
def test_no_image_without_a_date_ever_gets_a_deadline(name, stack):
    """Global Constraint: a deadline is never invented."""
    cfg, engine, llm, _ = stack
    want = json.loads((EXPECTED / f"{name}.json").read_text(encoding="utf-8"))
    if (want["lens"] != "document" or want.get("deadline") is not None
            or not want["readable"]):
        pytest.skip("only applies to readable documents with no real deadline")
    ocr = read_korean(_image_for(name), engine, cfg.min_hangul)
    card, _ = extract_document(ocr.text, llm)
    assert card.deadline is None, f"{name}: invented {card.deadline}"
