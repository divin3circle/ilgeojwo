"""One normalisation, used for both patterns and text, so they cannot diverge.

NFKC rather than NFC: Korean packaging and CJK-locale OCR routinely emit
full-width Latin (ＩＢＵＰＲＯＦＥＮ), which NFC leaves alone and NFKC folds to
ASCII. Without it, a full-width ingredient name is a silent false negative.

Separators are stripped, not just whitespace. OCR breaks a long ingredient name
across lines with a hyphen, and PDF text layers carry soft hyphens and
zero-width characters. Every one of those would otherwise hide a warning.
"""

from __future__ import annotations

import re
import unicodedata

_STRIP = re.compile(
    "["
    r"\s"                            # space, tab, newline, NBSP, ideographic space
    "­"                         # soft hyphen
    "​-‏"                  # zero-width space / non-joiner / joiner / marks
    "⁠﻿"                   # word joiner, BOM
    r"\-‐-―−"         # hyphens, dashes, minus sign
    "·•‧∙・"  # middle dots and bullets
    "~"
    "]+"
)


def normalize(text: str) -> str:
    return _STRIP.sub("", unicodedata.normalize("NFKC", text)).lower()
