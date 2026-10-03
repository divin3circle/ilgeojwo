# 읽어줘 (Ilgeojwo) — "read it to me"

Point a camera at anything Korean that has consequences, and get back what it
means for you and what you need to do.

Built for my sister, who is doing a Masters in South Korea, reads little Korean,
and has a pulmonary condition. Two things kept biting her:

- **Official paperwork** — immigration and ARC letters, university forms, bank
  notices, bills. Dense formal Korean, real deadlines, real consequences.
- **Medicine labels** — Korean over-the-counter cold and pain medicine routinely
  contains NSAIDs and decongestants, which are not neutral for someone with a
  respiratory condition. She gets handed a box she cannot read.

**Everything runs on her own laptop.** No API keys, no accounts, no uploads. Her
passport number, her address, her condition and her medication list never leave
the machine. It works with the WiFi switched off.

## Install

**macOS / Linux**

```bash
./setup.sh      # dependencies, language model, OCR models, tests
make run        # serves on your network and prints a QR code
```

**Windows** (PowerShell, in the repo folder)

```powershell
.\setup.ps1
uv run python -m ilgeojwo.serve
```

Setup picks the language model your machine can hold — **EXAONE 3.5 7.8B** on 12 GB
or more, **2.4B** below that — and records the choice in `.ilgeojwo.env` so the
server loads the model that was actually downloaded. The 7.8B mistranslates drug
names noticeably less, which matters here (see Licences and the limitations below).

**Graphics card:** OCR uses CUDA when a CUDA build of PyTorch is present, and the
CPU otherwise — a few seconds per photo either way. `uv sync` installs the CPU
build, so if you want the GPU:

```powershell
uv pip install --force-reinstall torch torchvision --index-url https://download.pytorch.org/whl/cu124
.\setup.ps1
```

Scan the QR code with your phone — on the same WiFi — and you are in. Photograph
a letter in the hallway; the laptop in the next room reads it.

**The link in the QR code contains a one-time key, and it is the only way in.**
The server has to listen on the whole network for your phone to reach it, and the
saved-scan list contains the full text of everything you have scanned — so anyone
on your WiFi who has that link can read it. Don't paste it anywhere. A fresh key
is minted every time you run `make run`.

## Swapping the model

The model is a config value, not a hard dependency. On a smaller laptop:

```bash
ILGEOJWO_LLM_MODEL=joonoh/HyperCLOVAX-SEED-Text-Instruct-1.5B make run
```

That is the whole change, and it is not hypothetical: this was written on an 8 GB
M2 running the 2.4B, and it runs on a 16 GB Windows laptop with a graphics card on
the 7.8B. Same code, same commit, one line of configuration. You cannot do that
when the model is someone else's HTTP endpoint.

## How it decides what to warn you about

**The model reads. A hand-written rule decides.**

A 2.4B model that invents a drug interaction could hurt someone. So the language
model is never allowed to make the safety call. Its only job on a medicine label
is transcription — pulling the printed ingredient names and dosage out of the OCR
text. Every warning comes from `src/ilgeojwo/risk/`, a deterministic matcher over
a curated rule file in `data/risk_rules.json` where every rule carries a citation.

The matcher runs against the **raw OCR text as well as** the model's extracted
ingredient list. If the model misses an ingredient entirely, the raw text still
raises the warning. A model failure can produce a false positive, not a silent
false negative.

**That guarantee is bounded, and the bound matters.** It holds for ingredient
names that are in the rule file, however badly the OCR mangles them — line
breaks, hyphenation, soft hyphens, zero-width characters, full-width Latin,
decomposed Hangul — and for **one** substituted character in a name of at least
four, because the OCR measurably does that. On a clean render of a cold-medicine
panel EasyOCR returned `이부프로편` for `이부프로펜` and `킬로르페니라민` for
`클로르페니라민` — and **two of three warnings, including the NSAID, were found
only by that tier.** Exact matching alone would have shown a clean card for a box
containing ibuprofen. The numbers are in
[`docs/spike-findings.md`](docs/spike-findings.md). Approximate matches are
labelled `POSSIBLE — the OCR may have misread this`.

It does **not** hold for an ingredient the rule file does not list, for two or
more substitutions, or for a short name misread. Treat a clean result as
"nothing on my list was found", never as "this is safe" — the tool says exactly
that on screen rather than leaving you to infer it.

A matched name also does not prove the box *contains* that ingredient — Korean
packaging names other drugs in its 주의사항 (precautions) paragraph. That is why
the warnings say a name "is named on this packaging" and show you what matched,
rather than asserting what the box contains.

## Footprint

Measured on an M2 MacBook Air with 8 GB RAM:

| | |
|---|---|
| EXAONE 3.5 2.4B (4-bit, via Ollama) | 1.6 GB on disk |
| EasyOCR Korean + English models | ~100 MB in `~/.EasyOCR` |
| Peak resident memory, both loaded | 1.14 GB |
| One page of OCR, models cached | 3.4 s |

The first `./setup.sh` downloads the EasyOCR models; after that it runs offline.
PaddleOCR-VL's 1.78 GB is **not** downloaded by default — it is selectable but
does not currently load (see Licences and `docs/spike-findings.md`).

Runtime measurements and the limits found while building are in
[`docs/spike-findings.md`](docs/spike-findings.md), including what is not yet
verified.

## Licences

Verified from the artifacts, not assumed:

- **PaddleOCR-VL-1.6** — Apache 2.0.
- **EXAONE 3.5** — *EXAONE AI Model License Agreement 1.1 - NC*. The **NC** is
  real: LG's licence restricts commercial use. That is fine for a tool built for
  one person, and it is why this repository is not a product.
- **HyperCLOVAX-SEED** (Naver) — published under Naver's own model licence, which
  permits commercial use for the variants Naver documents as such. Read the terms
  for the specific model before relying on it; this project does not vouch for
  them.

This project's own code is MIT.

## Not medical advice

The label lens is a **reading aid**. It does not know your medical history, it
does not diagnose, and it never recommends a dose. It tells you what is printed
on the box and flags ingredients against a list you control, then tells you to
ask your pharmacist or doctor. Always do that.
