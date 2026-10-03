"""Production wiring: the configured OCR engine, the real Ollama client."""

from ..config import load_config
from ..extract.extractor import OllamaClient
from ..ocr.reader import build_ocr_engine
from .app import create_app


def app():
    cfg = load_config()
    return create_app(cfg, build_ocr_engine(cfg),
                      OllamaClient(cfg.ollama_url, cfg.llm_model))
