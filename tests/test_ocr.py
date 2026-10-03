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


def test_low_confidence_boxes_are_dropped_so_the_readability_gate_means_something():
    """EasyOCR decodes from a charset of precomposed syllables, so an upside-down
    page yields plenty of confident-looking 가-힣 garbage rather than the isolated
    jamo this module's docstring once assumed. Per-box confidence is the only
    discriminator available, and `detail=0` was throwing it away."""
    from ilgeojwo.ocr.reader import keep_confident
    rows = [(None, "이부프로펜", 0.91), (None, "믜컕둏", 0.07), (None, "200mg", 0.74)]
    assert keep_confident(rows, 0.3) == "이부프로펜\n200mg"


def test_keep_confident_survives_malformed_rows():
    from ilgeojwo.ocr.reader import keep_confident
    assert keep_confident([None, (), ("x",), (None, "ok", 0.9)], 0.3) == "ok"


def test_the_engine_is_only_constructed_once_under_concurrency():
    """Two concurrent first requests would otherwise each build a Reader and
    double the memory against the 3 GB budget."""
    import threading
    from ilgeojwo.ocr.reader import EasyOcrEngine
    engine = EasyOcrEngine()
    built = []

    def fake_build():
        built.append(1)
        return object()

    engine._build = fake_build
    threads = [threading.Thread(target=engine._ensure_reader) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(built) == 1


def test_confidence_is_a_weak_filter_so_structure_does_the_work():
    """MEASURED on the cold-medicine fixture: the correct ingredient line
    '킬로르페니라민말레산염 2mg' scored 0.37 while the garbage box '[' scored 0.53.
    Confidence therefore cannot separate real text from noise here — a floor high
    enough to drop the garbage also drops the ingredient. So the floor only
    removes degenerate boxes, and single-character non-word boxes go by shape."""
    from ilgeojwo.ocr.reader import keep_confident
    rows = [(None, "킬로르페니라민말레산염 2mg", 0.37), (None, "[", 0.53),
            (None, "·", 0.91), (None, "", 0.99)]
    assert keep_confident(rows, 0.05) == "킬로르페니라민말레산염 2mg"
