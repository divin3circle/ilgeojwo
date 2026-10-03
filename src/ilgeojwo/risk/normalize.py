"""One normalisation, used for both patterns and text, so they cannot diverge."""

from __future__ import annotations

import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")


def normalize(text: str) -> str:
    return _WHITESPACE.sub("", unicodedata.normalize("NFC", text)).lower()
