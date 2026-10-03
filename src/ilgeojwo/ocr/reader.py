"""Image in, Korean text out. Knows nothing about lenses, cards, or risk."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

# Precomposed Hangul syllables only. Isolated jamo (ㄱ, ᅡ) are what a rotated
# or out-of-focus photo produces, so they deliberately do not count.
_HANGUL_SYLLABLE = re.compile(r"[가-힣]")


@dataclass(frozen=True)
class OcrResult:
    text: str
    readable: bool


class OcrEngine(Protocol):
    def read(self, path: Path) -> str: ...


def read_korean(path: Path, engine: OcrEngine, min_hangul: int) -> OcrResult:
    text = engine.read(path)
    return OcrResult(text=text, readable=len(_HANGUL_SYLLABLE.findall(text)) >= min_hangul)


class PaddleOcrVlEngine:
    """Real engine. Loaded lazily so importing this module costs nothing."""

    def __init__(self, model_id: str) -> None:
        self._model_id = model_id
        self._proc = None
        self._model = None

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
