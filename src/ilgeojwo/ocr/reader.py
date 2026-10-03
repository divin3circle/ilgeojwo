"""Image in, Korean text out. Knows nothing about lenses, cards, or risk.

Two engines, chosen by config. EasyOCR is the default because it works:
PaddleOCR-VL-1.6 scores better on paper, but its `trust_remote_code` modeling
file calls `ROPE_INIT_FUNCTIONS['default']`, and that key exists in no
transformers 5.x release — while the model card requires `transformers>=5.0.0`
for that very backend. It is kept here, selectable, in case upstream fixes it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:  # avoids a runtime dependency from ocr/ onto config
    from ..config import Config

# Precomposed Hangul syllables only. Isolated jamo (ㄱ, ᅡ) are what a rotated
# or out-of-focus photo produces, so they deliberately do not count.
_HANGUL_SYLLABLE = re.compile(r"[가-힣]")

ENGINES = ("easyocr", "paddleocr-vl")


@dataclass(frozen=True)
class OcrResult:
    text: str
    readable: bool


class OcrEngine(Protocol):
    @property
    def loaded(self) -> bool: ...

    def read(self, path: Path) -> str: ...


def read_korean(path: Path, engine: OcrEngine, min_hangul: int) -> OcrResult:
    text = engine.read(path)
    return OcrResult(text=text, readable=len(_HANGUL_SYLLABLE.findall(text)) >= min_hangul)


class EasyOcrEngine:
    """Default engine. CPU-only, Korean + English, no transformers dependency."""

    def __init__(self, languages: list[str] | None = None) -> None:
        self._languages = list(languages or ["ko", "en"])
        self._reader = None

    @property
    def loaded(self) -> bool:
        return self._reader is not None

    def read(self, path: Path) -> str:
        import easyocr

        if self._reader is None:
            self._reader = easyocr.Reader(self._languages, gpu=False, verbose=False)
        lines = self._reader.readtext(str(path), detail=0, paragraph=True)
        return "\n".join(str(line) for line in lines)


class PaddleOcrVlEngine:
    """Better on paper, currently broken upstream. See the module docstring."""

    def __init__(self, model_id: str) -> None:
        self._model_id = model_id
        self._proc = None
        self._model = None

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def _load(self) -> None:
        if self._model is not None:
            return
        from transformers import AutoModelForCausalLM, AutoProcessor

        self._proc = AutoProcessor.from_pretrained(self._model_id, trust_remote_code=True)
        self._model = AutoModelForCausalLM.from_pretrained(
            self._model_id, trust_remote_code=True
        )

    def read(self, path: Path) -> str:
        from PIL import Image

        self._load()
        img = Image.open(path).convert("RGB")
        inputs = self._proc(images=img, text="OCR:", return_tensors="pt")
        out = self._model.generate(**inputs, max_new_tokens=2048)
        return self._proc.batch_decode(out, skip_special_tokens=True)[0]


def build_ocr_engine(config: Config) -> OcrEngine:
    """Constructs the engine without loading any weights."""
    if config.ocr_engine == "easyocr":
        return EasyOcrEngine()
    if config.ocr_engine == "paddleocr-vl":
        return PaddleOcrVlEngine(config.ocr_model)
    raise ValueError(
        f"unknown ILGEOJWO_OCR_ENGINE {config.ocr_engine!r}; "
        f"valid options: {', '.join(ENGINES)}"
    )
