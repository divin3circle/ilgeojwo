"""Load and validate the curated rule file. Rejects anything unshippable."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Rule:
    id: str
    severity: str
    match_ko: tuple[str, ...]
    match_en: tuple[str, ...]
    message_en: str
    source: str


def load_rules(path: Path) -> tuple[Rule, ...]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rules: list[Rule] = []
    for raw in data["rules"]:
        rule = Rule(
            id=raw["id"],
            severity=raw["severity"],
            match_ko=tuple(raw.get("match_ko", ())),
            match_en=tuple(raw.get("match_en", ())),
            message_en=raw["message_en"],
            source=raw.get("source", ""),
        )
        if not rule.source.strip():
            raise ValueError(f"rule {rule.id!r} has no source citation")
        if not (rule.match_ko or rule.match_en):
            raise ValueError(f"rule {rule.id!r} has no match pattern")
        rules.append(rule)
    return tuple(rules)
