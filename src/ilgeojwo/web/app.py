"""HTTP and one page. Renders what it is given; decides nothing."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from ..config import Config
from ..extract.extractor import LlmClient, ModelUnavailable, extract_document
from ..ocr.reader import OcrEngine, read_korean
from ..store.db import list_scans, save_scan

UNREADABLE = "Couldn't read this — try more light, a flatter angle, or move closer."
LENSES = {"document", "label"}
_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def create_app(config: Config, ocr_engine: OcrEngine, llm: LlmClient) -> FastAPI:
    app = FastAPI(title="읽어줘")
    uploads = config.db_path.parent / "uploads"

    @app.get("/")
    def index(request: Request):
        return _TEMPLATES.TemplateResponse(request, "index.html", {})

    @app.get("/scans")
    def scans():
        return list_scans(config.db_path)

    @app.post("/scan")
    async def scan(image: UploadFile = File(...), lens: str = Form(...)):
        if lens not in LENSES:
            raise HTTPException(422, f"unknown lens: {lens!r}")

        uploads.mkdir(parents=True, exist_ok=True)
        saved = uploads / f"{uuid.uuid4().hex}{Path(image.filename or '').suffix}"
        with saved.open("wb") as fh:
            shutil.copyfileobj(image.file, fh)

        ocr = read_korean(saved, ocr_engine, config.min_hangul)
        if not ocr.readable:
            # The model is never asked to interpret noise.
            save_scan(config.db_path, lens=lens, image_path=str(saved),
                      ocr_text=ocr.text, card_json="{}", status="unreadable")
            return JSONResponse({"status": "unreadable", "message": UNREADABLE,
                                 "card": None, "ocr_text": ocr.text})

        try:
            card, status = extract_document(ocr.text, llm)
        except ModelUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        card_json = card.model_dump_json()
        save_scan(config.db_path, lens=lens, image_path=str(saved),
                  ocr_text=ocr.text, card_json=card_json, status=status)
        return JSONResponse({"status": status, "message": "",
                             "card": json.loads(card_json), "ocr_text": ocr.text})

    return app
