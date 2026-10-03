import unicodedata

from ilgeojwo.risk.normalize import normalize


def test_whitespace_is_removed_because_korean_ocr_spacing_is_unreliable():
    assert normalize("이부 프로펜") == normalize("이부프로펜")


def test_a_name_split_across_a_line_break_still_matches():
    """Review Focus 3. Newlines are the common OCR break on a narrow box panel.
    If this fails, a high-severity warning silently disappears."""
    assert normalize("이부\n프로펜") == normalize("이부프로펜")
    assert normalize("ibu-\nprofen").replace("-", "") == normalize("ibuprofen")


def test_tabs_and_nonbreaking_spaces_are_removed_too():
    assert normalize("이부\t프로 펜") == normalize("이부프로펜")


def test_decomposed_hangul_matches_composed_hangul():
    decomposed = unicodedata.normalize("NFD", "이부프로펜")
    assert normalize(decomposed) == normalize("이부프로펜")


def test_english_is_lowercased_so_case_never_hides_a_warning():
    assert normalize("IBUPROFEN") == normalize("ibuprofen")


def test_empty_input_is_empty_output():
    assert normalize("") == ""
