#!/usr/bin/env bash
# One command to make this laptop ready. Safe to re-run.
set -euo pipefail

command -v uv >/dev/null || { echo "Install uv: https://docs.astral.sh/uv/"; exit 1; }
command -v ollama >/dev/null || { echo "Install Ollama: https://ollama.com/download"; exit 1; }

MODEL="${ILGEOJWO_LLM_MODEL:-exaone3.5:2.4b}"

echo "==> Python dependencies"
uv sync

echo "==> Language model: $MODEL"
pgrep -x ollama >/dev/null || { ollama serve >/dev/null 2>&1 & sleep 3; }
ollama pull "$MODEL"

echo "==> OCR weights (first run downloads ~1 GB)"
uv run python -c "
from ilgeojwo.config import load_config
from transformers import AutoProcessor
AutoProcessor.from_pretrained(load_config().ocr_model, trust_remote_code=True)
print('ok')
"

echo "==> Tests"
uv run pytest -q

echo
echo "Ready. Run:  make run"
