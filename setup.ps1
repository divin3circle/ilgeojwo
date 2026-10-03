#Requires -Version 5.1
# One command to make a Windows laptop ready. Safe to re-run.
$ErrorActionPreference = "Stop"

function Need($cmd, $hint) {
  if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
    Write-Host "Missing: $cmd" -ForegroundColor Red
    Write-Host "  $hint"
    exit 1
  }
}

Need uv     "Install uv:     winget install astral-sh.uv   (or https://docs.astral.sh/uv/)"
Need ollama "Install Ollama: https://ollama.com/download"

Write-Host "==> Python dependencies"
uv sync
if ($LASTEXITCODE -ne 0) { Write-Host "uv sync failed. Fix the error above and re-run." -ForegroundColor Red; exit 1 }

# Pick the model this machine can actually hold. A 16 GB laptop runs the 7.8B
# comfortably and it mistranslates drug names far less than the 2.4B.
$ramGB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
if ($env:ILGEOJWO_LLM_MODEL) {
  $model = $env:ILGEOJWO_LLM_MODEL
} elseif ($ramGB -ge 12) {
  $model = "exaone3.5:7.8b"
} else {
  $model = "exaone3.5:2.4b"
}
Write-Host "==> $ramGB GB RAM detected -> language model $model"

Write-Host "==> Waiting for Ollama"
$ok = $false
foreach ($i in 1..30) {
  try { Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing -TimeoutSec 2 | Out-Null; $ok = $true; break }
  catch { Start-Sleep -Seconds 1 }
}
if (-not $ok) {
  Write-Host "Ollama is not answering on port 11434." -ForegroundColor Red
  Write-Host "  Open the Ollama app (or run 'ollama serve') and re-run this script."
  exit 1
}

ollama pull $model
if ($LASTEXITCODE -ne 0) { Write-Host "Could not pull $model. Check your connection and re-run." -ForegroundColor Red; exit 1 }

Write-Host "==> Graphics card"
$gpu = (uv run python -c "import torch; print('1' if torch.cuda.is_available() else '0')").Trim()
if ($gpu -eq "1") {
  Write-Host "    CUDA is available - OCR will use the graphics card."
} else {
  Write-Host "    No CUDA-enabled PyTorch found, so OCR will run on the CPU (a few seconds per photo)."
  Write-Host "    That is fine. To use your graphics card instead, install a CUDA build of PyTorch:"
  Write-Host "      uv pip install --force-reinstall torch torchvision --index-url https://download.pytorch.org/whl/cu124"
  Write-Host "    then re-run this script."
}

Write-Host "==> Recording these choices in .ilgeojwo.env"
"ILGEOJWO_LLM_MODEL=$model`r`nILGEOJWO_OCR_GPU=$gpu`r`n" | Set-Content -Encoding UTF8 ".ilgeojwo.env"

Write-Host "==> OCR models (first run downloads about 100 MB; after this it works offline)"
uv run python -c @"
from ilgeojwo.config import load_config
from ilgeojwo.env import FILENAME, load_env_file
from ilgeojwo.ocr.reader import build_ocr_engine
from PIL import Image
import os, pathlib, tempfile
load_env_file(pathlib.Path(FILENAME), os.environ)
cfg = load_config()
engine = build_ocr_engine(cfg)
with tempfile.TemporaryDirectory() as d:
    p = pathlib.Path(d) / 'warm.png'
    Image.new('RGB', (64, 32), 'white').save(p)
    engine.read(p)
print('ok:', cfg.ocr_engine, 'gpu=', engine.gpu)
"@
if ($LASTEXITCODE -ne 0) { Write-Host "Could not prepare the OCR engine. Re-run with a connection." -ForegroundColor Red; exit 1 }

Write-Host "==> Tests"
uv run pytest -q
if ($LASTEXITCODE -ne 0) { Write-Host "Tests failed. Do not rely on the tool until this is fixed." -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "Ready. Start it with:" -ForegroundColor Green
Write-Host "  uv run python -m ilgeojwo.serve"
Write-Host ""
Write-Host "Then scan the QR code with your phone, on the same WiFi."
