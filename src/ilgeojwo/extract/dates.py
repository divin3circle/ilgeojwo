"""Korean date parsing. Returns None whenever a date would have to be invented.

A missing year is an inference, and spec §3.1 forbids inferring deadlines, so
yearless dates yield None. The verbatim Korean text is always shown to the
user, so nothing is hidden from her — it is only not stored as a fact.
"""

from __future__ import annotations

import re
from datetime import date

# A plausibility window. Outside it, a 2026->7026 misread or a 단기 4359 era year
# would otherwise display and sort as a real deadline.
_MIN_YEAR, _MAX_YEAR = 2000, 2100

# Characters that mean the digits are part of a reference number, not a date:
# 제2026-10-05호, 출입국-2026-09-30.
_PREFIX_REJECT = "제-\u2010\u2011\u2012\u2013\u2014\u2015"

_PATTERNS = (
    re.compile(r"(?P<y>\d{4})\s*년\s*(?P<m>\d{1,2})\s*월\s*(?P<d>\d{1,2})\s*일"),
    re.compile(r"(?P<y>\d{4})\s*[.\-/]\s*(?P<m>\d{1,2})\s*[.\-/]\s*(?P<d>\d{1,2})"),
)


def _is_reference_number(text: str, match: re.Match) -> bool:
    before = text[:match.start()].rstrip()
    after = text[match.end():].lstrip()
    return bool(before and before[-1] in _PREFIX_REJECT) or after[:1] == "호"


def parse_korean_date(text: str) -> date | None:
    """Returns the LAST plausible date in the string.

    Korean writes a deadline as the end of a range (접수기간 A~B), and the model
    is asked for the deadline "exactly as written", so a range is the expected
    input rather than an edge case.
    """
    if not text:
        return None
    found: list[tuple[int, date]] = []
    for pattern in _PATTERNS:
        for m in pattern.finditer(text):
            year = int(m.group("y"))
            if not _MIN_YEAR <= year <= _MAX_YEAR:
                continue
            if _is_reference_number(text, m):
                continue
            try:
                found.append((m.start(), date(year, int(m.group("m")), int(m.group("d")))))
            except ValueError:
                continue  # impossible calendar date — keep looking
    return max(found)[1] if found else None
