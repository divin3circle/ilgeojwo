"""Load and validate the curated rule file.

She is invited to edit this file (spec §4.2), so validation is strict and every
message names the offending rule. Two failure modes are rejected outright
because they are silent: a rule file with no rules disables every warning, and a
pattern that normalises to nothing matches every input.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .normalize import normalize

SEVERITIES = ("high", "medium", "low")


@dataclass(frozen=True)
class Rule:
    id: str
    severity: str
    match_ko: tuple[str, ...]
    match_en: tuple[str, ...]
    message_en: str
    source: str


def _patterns(raw: dict, rule_id: str, field: str) -> tuple[str, ...]:
    value = raw.get(field, [])
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValueError(
            f"rule {rule_id!r}: {field!r} must be a list of strings, "
            f"got {type(value).__name__} — a bare string becomes one pattern per character"
        )
    out: list[str] = []
    for pattern in value:
        if not isinstance(pattern, str):
            raise ValueError(f"rule {rule_id!r}: {field!r} has a non-string pattern {pattern!r}")
        if not normalize(pattern):
            raise ValueError(
                f"rule {rule_id!r}: {field!r} has a pattern that normalises to nothing "
                f"({pattern!r}) — it would match every input"
            )
        out.append(pattern)
    return tuple(out)


def load_rules(path: Path) -> tuple[Rule, ...]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "rules" not in data:
        raise ValueError(f"{path}: no 'rules' key")

    raw_rules = data["rules"]
    if not isinstance(raw_rules, list) or not raw_rules:
        raise ValueError(
            f"{path}: 'rules' is empty — that would silently disable every warning"
        )

    rules: list[Rule] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_rules):
        if not isinstance(raw, dict):
            raise ValueError(f"rule #{index}: expected an object, got {type(raw).__name__}")

        rule_id = raw.get("id")
        if not isinstance(rule_id, str) or not rule_id.strip():
            raise ValueError(f"rule #{index}: 'id' must be a non-empty string, got {rule_id!r}")
        if rule_id in seen:
            raise ValueError(f"rule {rule_id!r}: duplicate id")
        seen.add(rule_id)

        severity = raw.get("severity")
        if severity not in SEVERITIES:
            raise ValueError(
                f"rule {rule_id!r}: 'severity' must be one of {SEVERITIES}, got {severity!r}"
            )

        message = raw.get("message_en")
        if not isinstance(message, str) or not message.strip():
            raise ValueError(
                f"rule {rule_id!r}: 'message_en' must be a non-empty string, got {message!r}"
            )

        source = raw.get("source")
        if not isinstance(source, str) or not source.strip():
            raise ValueError(
                f"rule {rule_id!r}: a 'source' citation is required, got {source!r}"
            )

        match_ko = _patterns(raw, rule_id, "match_ko")
        match_en = _patterns(raw, rule_id, "match_en")
        if not (match_ko or match_en):
            raise ValueError(f"rule {rule_id!r}: has no match pattern")

        rules.append(Rule(rule_id, severity, match_ko, match_en, message, source))

    return tuple(rules)
