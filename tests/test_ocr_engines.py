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


@pytest.mark.parametrize("setting,expected", [
    ("1", True), ("true", True), ("TRUE", True), ("yes", True),
    ("0", False), ("false", False), ("no", False), ("", False),
])
def test_an_explicit_gpu_setting_is_honoured_without_probing_hardware(setting, expected):
    from ilgeojwo.ocr.reader import resolve_gpu
    assert resolve_gpu(setting) is expected


def test_auto_defers_to_whether_cuda_is_actually_present(monkeypatch):
    from ilgeojwo.ocr import reader
    monkeypatch.setattr(reader, "_cuda_available", lambda: True)
    assert reader.resolve_gpu("auto") is True
    monkeypatch.setattr(reader, "_cuda_available", lambda: False)
    assert reader.resolve_gpu("auto") is False


def test_the_engine_carries_the_gpu_setting_from_config():
    from ilgeojwo.ocr.reader import EasyOcrEngine, build_ocr_engine
    engine = build_ocr_engine(load_config(env={"ILGEOJWO_OCR_GPU": "0"}))
    assert isinstance(engine, EasyOcrEngine)
    assert engine.gpu is False
    assert engine.loaded is False
