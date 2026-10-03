#!/usr/bin/env bash
# One command to make this laptop ready. Safe to re-run.
set -euo pipefail

command -v uv >/dev/null || { echo "Install uv: https://docs.astral.sh/uv/"; exit 1; }
command -v ollama >/dev/null || { echo "Install Ollama: https://ollama.com/download"; exit 1; }

# Pick the model this machine can hold. The 7.8B mistranslates drug names far
# less than the 2.4B, and a 12 GB+ laptop runs it comfortably.
RAM_GB=$(( $(sysctl -n hw.memsize 2>/dev/null || echo 0) / 1073741824 ))
[ "$RAM_GB" -eq 0 ] && RAM_GB=$(( $(getconf _PHYS_PAGES 2>/dev/null || echo 0) * $(getconf PAGE_SIZE 2>/dev/null || echo 4096) / 1073741824 ))
if [ -n "${ILGEOJWO_LLM_MODEL:-}" ]; then
  MODEL="$ILGEOJWO_LLM_MODEL"
elif [ "$RAM_GB" -ge 12 ]; then
  MODEL="exaone3.5:7.8b"
else
  MODEL="exaone3.5:2.4b"
fi
echo "==> ${RAM_GB} GB RAM detected -> language model $MODEL"

echo "==> Python dependencies"
uv sync

echo "==> Language model: $MODEL"
pgrep -x ollama >/dev/null || { ollama serve >/dev/null 2>&1 & }

echo "==> Ollama"
for _ in $(seq 1 30); do
  curl -sf http://localhost:11434/api/tags >/dev/null && break || sleep 1
done
curl -sf http://localhost:11434/api/tags >/dev/null || {
  echo "Ollama is not answering on :11434. Start it with 'ollama serve' and re-run."
  exit 1
}
ollama pull "$MODEL" || { echo "Could not pull $MODEL. Check your connection, then re-run."; exit 1; }

echo "==> Recording these choices in .ilgeojwo.env"
GPU=$(uv run python -c "import torch; print('1' if torch.cuda.is_available() else '0')" 2>/dev/null || echo 0)
printf 'ILGEOJWO_LLM_MODEL=%s\nILGEOJWO_OCR_GPU=%s\n' "$MODEL" "$GPU" > .ilgeojwo.env

echo "==> OCR weights for the CONFIGURED engine (first run downloads ~100 MB)"
uv run python -c "
from ilgeojwo.config import load_config
from ilgeojwo.ocr.reader import build_ocr_engine
from PIL import Image
import tempfile, pathlib
cfg = load_config()
engine = build_ocr_engine(cfg)
with tempfile.TemporaryDirectory() as d:
    p = pathlib.Path(d) / 'warm.png'
    Image.new('RGB', (64, 32), 'white').save(p)
    engine.read(p)
print('ok:', cfg.ocr_engine)
" || { echo "Could not prepare the OCR engine. Re-run with a connection; after this it works offline."; exit 1; }

echo "==> Tests"
uv run pytest -q

echo
echo "Ready. Run:  make run"
