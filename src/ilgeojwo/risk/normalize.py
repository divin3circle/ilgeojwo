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

# Runs that join two separate things on a label: spaces, newlines, Korean's
# enumeration middle dot, bullets. Deleting these lets 살리실산 + 메틸파라벤 fuse
# into 살리실산메틸, so `bounded()` turns them into a boundary instead.
_BOUNDARY = re.compile("[\\s\u00b7\u2022\u2027\u2219\u30fb]+")

# Deleted outright: hyphenation and invisibles are *inside* one name when OCR
# breaks it across a line.
_JOINERS = re.compile(
    "["
    "\u00ad"
    "\u200b-\u200f"
    "\u2060\ufeff"
    r"\-\u2010-\u2015\u2212"
    "~"
    "]+"
)

BOUNDARY = "\x00"

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
    """Fuses everything. Required by Review Focus 3: OCR breaks a single name
    across a line, and the pieces must rejoin."""
    return _STRIP.sub("", unicodedata.normalize("NFKC", text)).lower()


def bounded(text: str) -> str:
    """Like normalize, but keeps separators as an impassable boundary.

    A hit here is genuinely one printed token; a hit that only appears in
    `normalize` output crossed a boundary and is reported as approximate.
    """
    folded = _JOINERS.sub("", unicodedata.normalize("NFKC", text))
    return _BOUNDARY.sub(BOUNDARY, folded).lower()
