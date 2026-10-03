"""HTTP and one page. Renders what it is given; decides nothing."""

from __future__ import annotations

import json
import shutil
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from ..config import Config
from ..events import ScanEvent, log_scan
from ..extract.extractor import (
    LlmClient, ModelUnavailable, extract_document, extract_label,
)
from ..ocr.reader import OcrEngine, read_korean
from ..risk.matcher import match_risks
from ..risk.rules import load_rules
from ..store.db import list_scans, save_scan

UNREADABLE = "Couldn't read this — try more light, a flatter angle, or move closer."
PARTIAL_LABEL = (
    "Only a little text came off this photo, so the card is incomplete — but what "
    "was read is flagged below. Take another photo of the ingredients panel too."
)
LENSES = {"document", "label"}
IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp",
               "image/heic", "image/heif", "image/tiff", "image/bmp"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _warning_dicts(warnings) -> list[dict]:
    return [{"rule_id": w.rule_id, "severity": w.severity, "message": w.message,
             "matched": list(w.matched), "found_in": list(w.found_in),
             "approximate": w.approximate} for w in warnings]


def create_app(config: Config, ocr_engine: OcrEngine, llm: LlmClient,
               token: str | None = None) -> FastAPI:
    app = FastAPI(title="읽어줘")
    uploads = config.db_path.parent / "uploads"
    # Loaded once, at startup, so a malformed rule file fails loudly here rather
    # than silently producing zero warnings on her first real scan.
    rules = load_rules(config.rules_path)

    def _authorise(request: Request) -> None:
        """She serves on 0.0.0.0 so her phone can reach it, and /scans returns the
        full OCR text of every document she has scanned. Korean share-houses
        commonly put every unit on one subnet."""
        if token and request.query_params.get("t") != token:
            raise HTTPException(401, "Open the link from the QR code on your laptop.")

    @app.get("/")
    def index(request: Request):
        _authorise(request)
        return _TEMPLATES.TemplateResponse(request, "index.html", {})

    @app.get("/scans")
    def scans(request: Request):
        _authorise(request)
        return list_scans(config.db_path)

    # Deliberately `def`, not `async def`: OCR and the Ollama call block, and on
    # the event loop they freeze the page itself for the whole scan. FastAPI runs
    # a sync handler in a threadpool.
    @app.post("/scan")
    def scan(request: Request, image: UploadFile = File(...), lens: str = Form(...)):
        _authorise(request)
        if lens not in LENSES:
            raise HTTPException(422, f"unknown lens: {lens!r}")

        content_type = (image.content_type or "").lower()
        if content_type not in IMAGE_TYPES:
            extra = (" PDFs are not supported yet — open the PDF and photograph "
                     "the page, or screenshot it." if "pdf" in content_type else "")
            raise HTTPException(
                415, f"That is a {content_type or 'file of unknown type'}, not a "
                     f"photo.{extra}")

        uploads.mkdir(parents=True, exist_ok=True)
        saved = uploads / f"{uuid.uuid4().hex}{Path(image.filename or '').suffix}"
        size = 0
        try:
            with saved.open("wb") as fh:
                while chunk := image.file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        raise HTTPException(
                            413, f"That photo is over "
                                 f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB. Your phone "
                                 f"camera can take a smaller one.")
                    fh.write(chunk)

            started = time.monotonic()
            ocr = read_korean(saved, ocr_engine, config.min_hangul)
            ocr_ms = int((time.monotonic() - started) * 1000)
        except HTTPException:
            saved.unlink(missing_ok=True)
            raise
        except ModelUnavailable as exc:
            saved.unlink(missing_ok=True)
            raise HTTPException(503, str(exc)) from exc
        except Exception as exc:
            # Spec §7: name the component and the fix. Never four words.
            saved.unlink(missing_ok=True)
            raise HTTPException(
                503,
                f"Could not read the image.\n"
                f"  {type(exc).__name__}: {exc}\n"
                f"  If this mentions a missing model file, run:  ./setup.sh\n"
                f"  If it mentions permissions, check that {uploads} is writable.",
            ) from exc

        if not ocr.readable:
            # The model is never asked to interpret noise — but the matcher is
            # pure logic and costs nothing, so a label scan is still screened.
            # Otherwise a blister foil reading exactly "이부프로펜 200mg" (five
            # syllables, below the gate) would be silently cleared.
            found = match_risks([], ocr.text, rules) if lens == "label" else []
            log_scan(ScanEvent(lens=lens, status="unreadable", ocr_ms=ocr_ms,
                               llm_ms=0, ocr_chars=len(ocr.text),
                               warnings=len(found),
                               approximate=sum(1 for w in found if w.approximate)))
            save_scan(config.db_path, lens=lens, image_path=str(saved),
                      ocr_text=ocr.text, card_json="{}", status="unreadable")
            return JSONResponse({
                "status": "unreadable",
                "message": PARTIAL_LABEL if found else UNREADABLE,
                "card": None,
                "warnings": _warning_dicts(found),
                "ocr_text": ocr.text,
            })

        llm_started = time.monotonic()
        try:
            if lens == "label":
                card, status = extract_label(ocr.text, llm, rules)
            else:
                card, status = extract_document(ocr.text, llm)
        except ModelUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        except Exception as exc:
            # Any other model failure — a read timeout on a slower laptop is the
            # likeliest — must still name the way out rather than 500.
            raise HTTPException(
                503,
                f"The language model failed while reading this.\n"
                f"  {type(exc).__name__}: {exc}\n"
                f"  On a slower laptop, switch to the smaller model:\n"
                f"    ILGEOJWO_LLM_MODEL=joonoh/HyperCLOVAX-SEED-Text-Instruct-1.5B make run",
            ) from exc

        llm_ms = int((time.monotonic() - llm_started) * 1000)
        warnings = getattr(card, "warnings", [])
        log_scan(ScanEvent(lens=lens, status=status, ocr_ms=ocr_ms, llm_ms=llm_ms,
                           ocr_chars=len(ocr.text), warnings=len(warnings),
                           approximate=sum(1 for w in warnings if w.get("approximate"))))
        card_json = card.model_dump_json()
        save_scan(config.db_path, lens=lens, image_path=str(saved),
                  ocr_text=ocr.text, card_json=card_json, status=status)
        return JSONResponse({"status": status, "message": "", "warnings": [],
                             "card": json.loads(card_json), "ocr_text": ocr.text})

    return app
