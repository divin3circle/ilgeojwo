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

```bash
./setup.sh      # dependencies, language model, OCR weights, tests
make run        # serves on your network and prints a QR code
```

Scan the QR code with your phone — on the same WiFi — and you are in. Photograph
a letter in the hallway; the laptop in the next room reads it.

## Swapping the model

The model is a config value, not a hard dependency. On a smaller laptop:

```bash
ILGEOJWO_LLM_MODEL=joonoh/HyperCLOVAX-SEED-Text-Instruct-1.5B make run
```

That is the whole change. You cannot do that when the model is someone else's
HTTP endpoint.

## How it decides what to warn you about

**The model reads. A hand-written rule decides.**

A 2.4B model that invents a drug interaction could hurt someone. So the language
model is never allowed to make the safety call. Its only job on a medicine label
is transcription — pulling the printed ingredient names and dosage out of the OCR
text. Every warning comes from `src/ilgeojwo/risk/`, a deterministic matcher over
a curated rule file in `data/risk_rules.json` where every rule carries a citation.

The matcher runs against the **raw OCR text as well as** the model's extracted
ingredient list. If the model misses an ingredient entirely, the raw text still
raises the warning. A model failure can produce a false positive. It cannot
silently produce a false negative.

## Footprint

Measured on an M2 MacBook Air with 8 GB RAM:

| | |
|---|---|
| EXAONE 3.5 2.4B (4-bit, via Ollama) | 1.6 GB on disk |
| PaddleOCR-VL-1.6 (`model.safetensors`) | 1.78 GB on disk |

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
