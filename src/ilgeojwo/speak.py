"""What to show the pharmacist when neither of you shares a language.

She is at the counter holding a box. She cannot ask her question in Korean; the
pharmacist cannot read her English. The tool already knows her condition and what
the scan just flagged, so it can put the question on screen in Korean and she
holds up the phone.

Every phrase comes from the rule file. No model, no network, and the same words
every time — which is the point: a chatbot that knows nothing about her cannot do
this, and would phrase it differently each time if it did.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .risk.rules import Rule


@dataclass(frozen=True)
class CounterPhrases:
    opening_ko: str
    opening_en: str
    condition_ko: str
    condition_en: str
    questions_ko: list[str] = field(default_factory=list)
    questions_en: list[str] = field(default_factory=list)


OPENING_KO = "실례합니다. 한국어를 잘 못합니다. 이 화면을 읽어 주시겠어요?"
OPENING_EN = "Excuse me. I do not speak Korean well. Could you read this screen?"

CONDITION_KO = "저는 폐 질환이 있습니다. 호흡에 영향을 주는 약은 피해야 합니다."
CONDITION_EN = ("I have a lung condition. I need to avoid medicines that affect "
                "breathing.")

CLOSING_KO = "이 약을 먹어도 괜찮을까요? 괜찮지 않다면 다른 약을 추천해 주세요."
CLOSING_EN = ("Is it safe for me to take this? If not, please recommend "
              "something else.")


def phrases_for(rule_ids: list[str], rules: tuple[Rule, ...]) -> CounterPhrases:
    """Korean to show, with the English she needs to know she is showing it."""
    wanted = list(dict.fromkeys(rule_ids or []))
    by_id = {rule.id: rule for rule in rules}

    questions_ko: list[str] = []
    questions_en: list[str] = []
    for rule_id in wanted:
        rule = by_id.get(rule_id)
        if rule is None or not rule.ask_ko:
            continue
        questions_ko.append(rule.ask_ko)
        questions_en.append(rule.ask_en or rule.ask_ko)

    return CounterPhrases(
        opening_ko=OPENING_KO,
        opening_en=OPENING_EN,
        condition_ko=CONDITION_KO,
        condition_en=CONDITION_EN,
        questions_ko=questions_ko,
        questions_en=questions_en,
    )
