from pathlib import Path

from ilgeojwo.config import load_config


def test_defaults_are_the_24b_korean_stack():
    c = load_config(env={})
    assert c.llm_model == "exaone3.5:2.4b"
    assert c.ocr_model == "PaddlePaddle/PaddleOCR-VL-1.6"
    assert c.ollama_url == "http://localhost:11434"
    assert c.min_hangul == 10


def test_the_whole_model_swap_is_one_environment_variable():
    """Spec §4.2: her laptop is weaker, so the swap must be trivial."""
    c = load_config(env={"ILGEOJWO_LLM_MODEL": "joonoh/HyperCLOVAX-SEED-Text-Instruct-1.5B"})
    assert c.llm_model == "joonoh/HyperCLOVAX-SEED-Text-Instruct-1.5B"
    assert c.ocr_model == "PaddlePaddle/PaddleOCR-VL-1.6"  # unchanged


def test_paths_are_overridable_so_tests_never_touch_real_data(tmp_path):
    c = load_config(env={"ILGEOJWO_DB": str(tmp_path / "t.db")})
    assert c.db_path == tmp_path / "t.db"


def test_config_is_immutable():
    import dataclasses

    import pytest

    c = load_config(env={})
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.llm_model = "something-else"


def test_the_ocr_engine_is_also_a_config_value():
    """The published PaddleOCR-VL transformers path is broken against every
    transformers 5.x, so the working engine is the default and the other stays
    selectable. Which engine reads the image must not be a code change."""
    assert load_config(env={}).ocr_engine == "easyocr"


def test_the_ocr_engine_can_be_switched_by_environment():
    c = load_config(env={"ILGEOJWO_OCR_ENGINE": "paddleocr-vl"})
    assert c.ocr_engine == "paddleocr-vl"
    assert c.llm_model == "exaone3.5:2.4b"  # unchanged
