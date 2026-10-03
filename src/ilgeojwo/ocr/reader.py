"""Image in, Korean text out. Knows nothing about lenses, cards, or risk.

Two engines, chosen by config. EasyOCR is the default because it works:
PaddleOCR-VL-1.6 scores better on paper, but its `trust_remote_code` modeling
file calls `ROPE_INIT_FUNCTIONS['default']`, and that key exists in no
transformers 5.x release — while the model card requires `transformers>=5.0.0`
for that very backend. It is kept here, selectable, in case upstream fixes it.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:  # avoids a runtime dependency from ocr/ onto config
    from ..config import Config

# Precomposed Hangul syllables only. Isolated jamo (ㄱ, ᅡ) are what a rotated
# or out-of-focus photo produces, so they deliberately do not count.
_HANGUL_SYLLABLE = re.compile(r"[가-힣]")

ENGINES = ("easyocr", "paddleocr-vl")

# University, bank and airline correspondence arrives as PDF. Each page is
# rendered and read in turn. The cap is low on purpose: reading 6 pages of an
# 8-page e-ticket produced 10,035 characters, which the model could not use at
# all, while page 1 alone carried the passenger, the flights and the total.
# Korean official documents front-load what matters.
# None means every page. The model is protected from the volume separately, by
# MAX_EXTRACT_CHARS in extract/extractor.py — the OCR text itself stays complete
# so the risk matcher and the verbatim Korean see the whole document.
MAX_PDF_PAGES: int | None = None
_PDF_RENDER_SCALE = 2.4  # roughly 170 dpi, enough for 9pt Korean

# Deliberately very low. Confidence looked like the discriminator between real
# Korean and OCR garbage, and measurement refuted that: on the cold-medicine
# fixture the correct line 킬로르페니라민말레산염 2mg scored 0.37 while the garbage
# box '[' scored 0.53. Any floor that drops the garbage drops the ingredient, so
# this only removes degenerate boxes and the shape check below does the real work.
MIN_BOX_CONFIDENCE = 0.05


_TRUTHY = {"1", "true", "yes", "on"}


def _cuda_available() -> bool:
    """Separate so tests can replace it without a GPU present."""
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def resolve_gpu(setting: str) -> bool:
    """"auto" asks the hardware; anything else is taken at its word.

    Her laptop is Windows with a graphics card, mine is an 8 GB M2 without one.
    The same configuration has to suit both.
    """
    value = (setting or "").strip().lower()
    if value == "auto":
        return _cuda_available()
    return value in _TRUTHY


def _is_noise(text: str) -> bool:
    """A lone bracket or dot is a detection artefact, not content."""
    stripped = text.strip()
    return len(stripped) <= 1 and not stripped.isalnum()


def keep_confident(rows: object, floor: float) -> str:
    """Joins box text, dropping degenerate boxes. Never raises on odd rows."""
    kept = []
    for row in rows or ():
        try:
            _, text, confidence = row[0], row[1], row[2]
        except (TypeError, IndexError, KeyError):
            continue
        if not isinstance(text, str) or _is_noise(text):
            continue
        if isinstance(confidence, (int, float)) and confidence >= floor:
            kept.append(text)
    return "\n".join(kept)


@dataclass(frozen=True)
class OcrResult:
    text: str
    readable: bool


class OcrEngine(Protocol):
    @property
    def loaded(self) -> bool: ...

    def read(self, path: Path) -> str: ...


def _render_pdf_pages(path: Path, into: Path, max_pages: int | None) -> list[Path]:
    """Renders up to max_pages to PNGs. Returns [] if it is not a readable PDF."""
    try:
        import pypdfium2
    except ImportError:
        return []
    try:
        document = pypdfium2.PdfDocument(path)
    except Exception:
        return []
    rendered: list[Path] = []
    try:
        wanted = len(document) if max_pages is None else min(len(document), max_pages)
        for index in range(wanted):
            page = document[index]
            image = page.render(scale=_PDF_RENDER_SCALE).to_pil()
            out = into / f"page-{index + 1:02d}.png"
            image.save(out)
            rendered.append(out)
    except Exception:
        return rendered
    finally:
        document.close()
    return rendered


def readable_enough(text: str, min_hangul: int) -> bool:
    return len(_HANGUL_SYLLABLE.findall(text)) >= min_hangul


def read_korean(path: Path, engine: OcrEngine, min_hangul: int,
                max_pdf_pages: int | None = MAX_PDF_PAGES,
                on_page=None) -> OcrResult:
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        import tempfile
        import time

        with tempfile.TemporaryDirectory() as workdir:
            pages = _render_pdf_pages(path, Path(workdir), max_pdf_pages)
            parts = []
            for number, page in enumerate(pages, start=1):
                started = time.monotonic()
                parts.append(engine.read(page))
                if on_page is not None:
                    on_page(number, len(pages), int((time.monotonic() - started) * 1000))
            text = "\n".join(parts)
    else:
        text = engine.read(path)
    return OcrResult(text=text, readable=readable_enough(text, min_hangul))


class EasyOcrEngine:
    """Default engine. CPU-only, Korean + English, no transformers dependency."""

    def __init__(self, languages: list[str] | None = None,
                 min_confidence: float = MIN_BOX_CONFIDENCE,
                 gpu: str | bool = False) -> None:
        self._languages = list(languages or ["ko", "en"])
        self._min_confidence = min_confidence
        self.gpu = gpu if isinstance(gpu, bool) else resolve_gpu(gpu)
        self._reader = None
        self._lock = threading.Lock()

    @property
    def loaded(self) -> bool:
        return self._reader is not None

    def _build(self):
        import warnings

        # EasyOCR builds a dynamically quantized model and PyTorch warns about
        # the deprecated API it uses. Nothing here can act on it, and it lands in
        # the terminal the user is reading for the pairing link.
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning, module=r"torch\.")
            warnings.filterwarnings("ignore", category=DeprecationWarning, module=r"torch\.")
            import easyocr

            return easyocr.Reader(self._languages, gpu=self.gpu, verbose=False)

    def _ensure_reader(self) -> None:
        # The handler runs in a threadpool, so two concurrent first requests
        # would otherwise each build a Reader and double the resident memory.
        if self._reader is not None:
            return
        with self._lock:
            if self._reader is None:
                self._reader = self._build()

    def read(self, path: Path) -> str:
        self._ensure_reader()
        # No rotation_info: it was added for upside-down phone photos and
        # measurably destroyed an ingredient line on an UPRIGHT image, replacing
        # 킬로르페니라민말레산염 2mg with '[' at higher confidence. Rotation handling
        # has to be earned with a rotated fixture, not assumed.
        rows = self._reader.readtext(str(path), detail=1, paragraph=False)
        return keep_confident(rows, self._min_confidence)


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
        return EasyOcrEngine(gpu=config.ocr_gpu)
    if config.ocr_engine == "paddleocr-vl":
        return PaddleOcrVlEngine(config.ocr_model)
    raise ValueError(
        f"unknown ILGEOJWO_OCR_ENGINE {config.ocr_engine!r}; "
        f"valid options: {', '.join(ENGINES)}"
    )
