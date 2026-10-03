import unicodedata

import pytest

from ilgeojwo.risk.normalize import normalize


def test_whitespace_is_removed_because_korean_ocr_spacing_is_unreliable():
    assert normalize("이부 프로펜") == normalize("이부프로펜")


@pytest.mark.parametrize("raw", [
    "이부\n프로펜",
    "이부-\n프로펜",
    "이부­프로펜",    # soft hyphen, common in PDF/OCR text layers
    "이부·프로펜",         # middle dot
    "이부‧프로펜",    # hyphenation point
    "이부–프로펜",    # en dash
    "이부\t프로 펜",  # tab + non-breaking space
    "이부​프로펜",    # zero-width space
    "이부‌프로펜",    # zero-width non-joiner
    "이부⁠프로펜",    # word joiner
    "이부﻿프로펜",    # BOM
    "이부　프로펜",    # ideographic space
])
def test_breaks_and_invisibles_never_hide_an_ingredient_name(raw):
    """Review Focus 3, and review findings C2/C3.

    Written WITHOUT pre-cleaning the input. The earlier version of this test
    called .replace('-', '') on normalize's OUTPUT, which did the
    implementation's job for it — so it passed green while the bug was live.
    """
    assert normalize(raw) == normalize("이부프로펜")


def test_latin_hyphenation_at_a_line_break_matches():
    assert normalize("ibu-\nprofen") == normalize("ibuprofen")
    assert normalize("ibu­profen") == normalize("ibuprofen")


def test_full_width_latin_folds_to_ascii():
    """Review C1: full-width Latin is routine on CJK packaging and in
    CJK-locale OCR output. NFC leaves it; NFKC folds it."""
    assert normalize("ＩＢＵＰＲＯＦＥＮ") == normalize("ibuprofen")


def test_full_width_digits_fold():
    assert normalize("２００ｍｇ") == normalize("200mg")


def test_decomposed_hangul_matches_composed_hangul():
    assert normalize(unicodedata.normalize("NFD", "이부프로펜")) == normalize("이부프로펜")


def test_english_is_lowercased_so_case_never_hides_a_warning():
    assert normalize("IBUPROFEN") == normalize("ibuprofen")


def test_empty_input_is_empty_output():
    assert normalize("") == ""


def test_a_separator_only_string_normalises_to_empty():
    """Guards against an always-fire rule: '' is a substring of everything,
    so a pattern made only of separators must be detectable as empty."""
    assert normalize(" -​·\n") == ""
