"""All tunable values in one place. Nothing else reads os.environ."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Config:
    ocr_engine: str
    ocr_gpu: str
    ocr_model: str
    llm_model: str
    ollama_url: str
    db_path: Path
    rules_path: Path
    min_hangul: int


def load_config(env: Mapping[str, str] | None = None) -> Config:
    e = os.environ if env is None else env
    return Config(
        ocr_engine=e.get("ILGEOJWO_OCR_ENGINE", "easyocr"),
        ocr_gpu=e.get("ILGEOJWO_OCR_GPU", "auto"),
        ocr_model=e.get("ILGEOJWO_OCR_MODEL", "PaddlePaddle/PaddleOCR-VL-1.6"),
        llm_model=e.get("ILGEOJWO_LLM_MODEL", "exaone3.5:2.4b"),
        ollama_url=e.get("ILGEOJWO_OLLAMA_URL", "http://localhost:11434"),
        db_path=Path(e.get("ILGEOJWO_DB", ROOT / "data" / "scans.db")),
        rules_path=Path(e.get("ILGEOJWO_RULES", ROOT / "data" / "risk_rules.json")),
        min_hangul=int(e.get("ILGEOJWO_MIN_HANGUL", "10")),
    )
