"""Korean date parsing. Returns None whenever a date would have to be invented.

A missing year is an inference, and spec §3.1 forbids inferring deadlines, so
yearless dates yield None. The verbatim Korean text is always shown to the
user, so nothing is hidden from her — it is only not stored as a fact.
"""

from __future__ import annotations

import re
from datetime import date

_PATTERNS = (
    re.compile(r"(?P<y>\d{4})\s*년\s*(?P<m>\d{1,2})\s*월\s*(?P<d>\d{1,2})\s*일"),
    re.compile(r"(?P<y>\d{4})\s*[.\-/]\s*(?P<m>\d{1,2})\s*[.\-/]\s*(?P<d>\d{1,2})"),
)


def parse_korean_date(text: str) -> date | None:
    if not text:
        return None
    for pattern in _PATTERNS:
        for m in pattern.finditer(text):
            try:
                return date(int(m.group("y")), int(m.group("m")), int(m.group("d")))
            except ValueError:
                continue  # impossible calendar date — keep looking
    return None
