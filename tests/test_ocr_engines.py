import pytest

from ilgeojwo.config import load_config
from ilgeojwo.ocr.reader import EasyOcrEngine, PaddleOcrVlEngine, build_ocr_engine


def test_the_default_config_builds_the_easyocr_engine():
    assert isinstance(build_ocr_engine(load_config(env={})), EasyOcrEngine)


def test_paddleocr_vl_is_still_selectable():
    cfg = load_config(env={"ILGEOJWO_OCR_ENGINE": "paddleocr-vl"})
    assert isinstance(build_ocr_engine(cfg), PaddleOcrVlEngine)


def test_an_unknown_engine_names_the_valid_options():
    cfg = load_config(env={"ILGEOJWO_OCR_ENGINE": "tesseract-maybe"})
    with pytest.raises(ValueError, match="easyocr"):
        build_ocr_engine(cfg)


def test_building_an_engine_loads_no_model():
    """`make run` must print the QR code immediately, not after a model load,
    and the test suite must never pull weights."""
    engine = build_ocr_engine(load_config(env={}))
    assert engine.loaded is False


def test_both_engines_satisfy_the_reader_protocol():
    for engine in (EasyOcrEngine(["ko", "en"]), PaddleOcrVlEngine("x/y")):
        assert callable(engine.read)
        assert engine.loaded is False
