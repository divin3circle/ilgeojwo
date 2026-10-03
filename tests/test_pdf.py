"""PDFs are what university, bank and airline correspondence actually arrives as."""

from pathlib import Path

from PIL import Image

from ilgeojwo.ocr.reader import read_korean


class CountingEngine:
    """Returns a different string per call, so page order is observable."""

    loaded = False

    def __init__(self, texts):
        self.texts = list(texts)
        self.calls = []

    def read(self, path):
        self.calls.append(Path(path))
        return self.texts.pop(0) if self.texts else ""


def _pdf(tmp_path: Path, pages: int) -> Path:
    first = Image.new("RGB", (600, 800), "white")
    rest = [Image.new("RGB", (600, 800), "white") for _ in range(pages - 1)]
    out = tmp_path / "doc.pdf"
    first.save(out, save_all=True, append_images=rest)
    return out


def test_a_pdf_is_read_page_by_page(tmp_path):
    engine = CountingEngine(["첫째 장 내용입니다", "둘째 장 내용입니다"])
    result = read_korean(_pdf(tmp_path, 2), engine, min_hangul=3)
    assert len(engine.calls) == 2
    assert "첫째" in result.text
    assert "둘째" in result.text
    assert result.readable is True


def test_each_page_is_rendered_to_its_own_image(tmp_path):
    engine = CountingEngine(["가나다라마바사", "아자차카타파하"])
    read_korean(_pdf(tmp_path, 2), engine, min_hangul=3)
    assert len({p.name for p in engine.calls}) == 2
    assert all(p.suffix == ".png" for p in engine.calls)


def test_a_long_pdf_is_capped_so_one_scan_cannot_take_an_hour(tmp_path):
    """The e-ticket that prompted this was 8 pages; OCR is seconds per page."""
    engine = CountingEngine(["가나다라마바사"] * 20)
    read_korean(_pdf(tmp_path, 20), engine, min_hangul=3, max_pdf_pages=4)
    assert len(engine.calls) == 4


def test_an_ordinary_image_is_still_read_directly(tmp_path):
    png = tmp_path / "a.png"
    Image.new("RGB", (40, 20), "white").save(png)
    engine = CountingEngine(["출입국관리사무소 체류기간 연장"])
    result = read_korean(png, engine, min_hangul=3)
    assert engine.calls == [png]
    assert "출입국" in result.text


def test_a_pdf_that_renders_to_nothing_is_unreadable_not_an_error(tmp_path):
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"not actually a pdf")
    result = read_korean(broken, CountingEngine([]), min_hangul=10)
    assert result.readable is False


def test_every_page_is_read_by_default(tmp_path):
    engine = CountingEngine(["가나다라마바사"] * 12)
    read_korean(_pdf(tmp_path, 12), engine, min_hangul=3)
    assert len(engine.calls) == 12


def test_progress_is_reported_per_page(tmp_path):
    """A 12-page scan takes minutes. Silence for minutes looks like a hang."""
    seen = []
    engine = CountingEngine(["가나다라마바사"] * 3)
    read_korean(_pdf(tmp_path, 3), engine, min_hangul=3,
                on_page=lambda i, total, ms: seen.append((i, total)))
    assert seen == [(1, 3), (2, 3), (3, 3)]


def test_an_explicit_cap_is_still_honoured(tmp_path):
    engine = CountingEngine(["가나다라마바사"] * 9)
    read_korean(_pdf(tmp_path, 9), engine, min_hangul=3, max_pdf_pages=2)
    assert len(engine.calls) == 2
