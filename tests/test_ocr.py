from pathlib import Path

from ilgeojwo.ocr.reader import OcrResult, read_korean


class FakeEngine:
    """Lets every OCR test run with no model and no network."""

    def __init__(self, text):
        self.text = text

    def read(self, path):
        return self.text


def test_korean_text_is_readable():
    r = read_korean(Path("x.jpg"), FakeEngine("출입국관리사무소 체류기간 연장허가 신청"), min_hangul=10)
    assert r.readable is True
    assert "출입국관리사무소" in r.text


def test_blank_image_is_unreadable_not_an_empty_card():
    """Review Focus 4."""
    assert read_korean(Path("x.jpg"), FakeEngine(""), min_hangul=10).readable is False


def test_her_thumb_is_unreadable():
    """Review Focus 4: a few stray glyphs must not count as a document."""
    assert read_korean(Path("x.jpg"), FakeEngine("ㅁ ㅇ"), min_hangul=10).readable is False


def test_an_english_receipt_is_unreadable_for_this_tool():
    """Review Focus 4: no Hangul means this is not what the tool is for."""
    r = read_korean(Path("x.jpg"), FakeEngine("TOTAL 12,000 THANK YOU"), min_hangul=10)
    assert r.readable is False


def test_rotated_photo_garbage_is_rejected_rather_than_passed_through():
    """Review Focus 2: an upside-down photo yields sparse noise, not a document.
    The failure must be visible, never silently 'ok'."""
    r = read_korean(Path("x.jpg"), FakeEngine("ᄀ ᅡ ᆫ\n\n ᄂ"), min_hangul=10)
    assert r.readable is False


def test_text_is_preserved_verbatim_including_whitespace():
    """Spec §3: the original Korean is always shown exactly as read."""
    raw = "제1항\n  납부기한\t2026년 10월 5일"
    assert read_korean(Path("x.jpg"), FakeEngine(raw), min_hangul=3).text == raw
