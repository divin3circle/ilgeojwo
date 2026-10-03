"""Production wiring: real OCR engine, real Ollama client."""

from ..config import load_config
from ..extract.extractor import OllamaClient
from ..ocr.reader import PaddleOcrVlEngine
from .app import create_app


def app():
    cfg = load_config()
    return create_app(cfg, PaddleOcrVlEngine(cfg.ocr_model),
                      OllamaClient(cfg.ollama_url, cfg.llm_model))
