# Spike findings

Hardware: Apple M2 MacBook Air, 8 GB RAM, macOS 25.6.

## Verified

| Component | Result |
|---|---|
| `transformers` | 5.18.0 — satisfies the `>=5.0.0` floor PaddleOCR-VL's transformers backend needs |
| `torch` | 2.14.1 (plus `torchvision` 0.29.1, `einops` 0.8.2) |
| EXAONE 3.5 2.4B via Ollama | pulled, 1.6 GB on disk, serving on `localhost:11434` |
| PaddleOCR-VL-1.6 licence | `apache-2.0` (HF model card metadata) |
| EXAONE 3.5 licence | `EXAONE AI Model License Agreement 1.1 - NC` — non-commercial (`ollama show --license`) |

## Transitive dependencies PaddleOCR-VL's remote code needs

Not documented in the model card; each surfaced only as an `ImportError` at
`AutoProcessor.from_pretrained` time, one per attempt:

1. `torchvision`
2. `einops`

Both are now pinned in `pyproject.toml`, so a fresh install does not hit them.

## Not yet verified

**OCR inference has not run.** `model.safetensors` is 1,917,255,968 bytes
(1.78 GB) and the measured blob throughput from this machine was **173 KB/s**,
putting the download at roughly three hours. The HF metadata API responded in
1.6 s, so this is the blob CDN over this particular connection, not the model
and not the project.

Consequences, stated plainly:

- End-to-end OCR quality is **unmeasured**, including on real phone photos
  (glare, skew, curved packaging). The readability gate in `ocr/reader.py` is
  unit-tested against fakes, not against real output.
- Peak resident memory with both models loaded is **unmeasured**. The projection
  is under 3 GB (≈1 GB OCR + ≈1.6 GB LLM at 4-bit) but no measurement supports
  that yet.

The design absorbs this: `ocr/` sits behind an `OcrEngine` protocol, so swapping
to EasyOCR or Tesseract is a one-class change with no effect on any other module.

## Synthetic test input

With her real photos not yet available, `/tmp/ilgeojwo/synthetic_doc.png` was
rendered locally (AppleSDGothicNeo, 34pt) standing in for an immigration notice:
sender, an action, `납부금액: 60,000원`, and `납부기한: 2026년 10월 5일`. A clean
render is a weak proxy for a phone photo and proves nothing about robustness.
