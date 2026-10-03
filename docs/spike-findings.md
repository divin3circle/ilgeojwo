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

---

## Resolution: PaddleOCR-VL is unusable; EasyOCR is the default

### PaddleOCR-VL-1.6 — three failures, the third fatal

1. `ImportError: torchvision` at `AutoProcessor.from_pretrained` — fixed by pinning it.
2. `ImportError: einops` — same, fixed.
3. `KeyError: 'default'` from `ROPE_INIT_FUNCTIONS[self.rope_type]` inside the
   model's `trust_remote_code` modeling file.

The third is not fixable by installing anything. I checked the registry in
transformers `v5.0.0`, `v5.5.0` and `v5.10.0`:

```
v5.0.0    linear dynamic yarn longrope llama3
v5.5.0    linear dynamic yarn longrope llama3 proportional
v5.10.0   linear dynamic yarn longrope llama3 proportional
```

No `'default'` in any of them — it was removed in the 5.0 major release — while
the model card requires `transformers>=5.0.0` for exactly this backend. The
published path cannot work on any supported version. Shimming it would mean
writing rope-initialisation maths by inference with no reference output to check
against, which is not a thing to guess at in a medical-adjacent tool.

Weights did download in full (1,917,255,968 bytes, exact match) after the inline
transformers download stalled and the `hf` CLI resumed it. Measured blob
throughput from this machine was 173 KB/s; the HF metadata API answered in 1.6 s,
so that was this connection, not the model.

`PaddleOcrVlEngine` stays in the tree, selectable with
`ILGEOJWO_OCR_ENGINE=paddleocr-vl`, in case upstream fixes it.

### EasyOCR — measured

| | |
|---|---|
| First `Reader(["ko","en"])` | 1047.9 s — download-dominated; models cache to `~/.EasyOCR` (~100 MB) |
| OCR of one page, cached | 3.4 s |
| Peak resident set | 1.14 GB — well inside the 3 GB budget |

Output on `synthetic_doc.png`, against the known source:

```
source:  체류기간 연장허가 … 신청서를 … 납부금액: 60,000원 … 납부기한: 2026년 10월 5일
easyocr: 체류기간 연장히가 … 신청서클 … 남부금액: 60,00o원 … 납부기한: 2026년 10월 5일
```

**The deadline is exact.** Three Hangul substitutions elsewhere: 허→히, 를→클,
납→남, plus `0`→`o`. On a clean render.

### What that measurement changed

The code reviewer graded "no fuzzy matching tier" as **Minor** and I accepted it.
This output re-grades it. Exact substring matching was the whole basis of the
safety claim, and the engine demonstrably substitutes syllables on easy input —
so `이부프로펜` read as `이부프로팬` would have produced no warning on a box that
really does contain an NSAID.

A single-substitution tier now runs when nothing matches exactly, for patterns of
at least four characters, and its warnings are rendered as `POSSIBLE — the OCR may
have misread this`. Short names stay exact-only so the tool does not cry wolf;
longer spellings of the same drug (`인산코데인` for `코데인`) still carry it.

Two false positives the tier introduced and how they are handled: a window
straddling two ingredient-list entries is rejected (otherwise `["에", "페드린"]`
matched `에페드린` one substitution away), and an exact hit always beats an
approximate one for the same rule, so a clean match is never downgraded.

### Golden run against the real stack

4 of 6 cases pass, including the immigration document on **both** deadline
(`2026-10-05`) and amount (`60,000`) — EXAONE recovered `60,000` from EasyOCR's
`60,00o원`, which is the division of labour working as designed: the OCR reads
badly, the language model cleans up, and neither is allowed near the safety call.

### The measurement that justifies the fuzzy tier

Running the matcher against EasyOCR's real output for the cold-medicine fixture:

```
rendered:  이부프로펜 200mg      슈도에페드린염산염 30mg      클로르페니라민말레산염 2mg
easyocr:   이부프로편 2OOmg      수도에페드린염산염 3Omg      킬로르페니라민말레산염 2mg
                  ^ 펜 -> 편          ^ 슈 -> 수                  ^ 클 -> 킬

[high  ] nsaid                   APPROXIMATE  matched=('이부프로펜',)
[medium] decongestant            exact        matched=('에페드린',)
[low   ] sedating_antihistamine  APPROXIMATE  matched=('클로르페니라민',)
```

**Two of the three warnings, including the high-severity NSAID, were found only by
the single-substitution tier.** Exact matching returned nothing for 이부프로편 or
킬로르페니라민. Before the tier existed, this fixture failed its golden test; the
tool would have shown a clean card for a box containing ibuprofen.

One incidental design lesson: `decongestant` matched *exactly* because the rule
list carries the short form `에페드린` as well as `슈도에페드린`, and the short
form survived inside the misread `수도에페드린염산염`. Listing both the bare drug
and its salt forms gives redundancy that costs nothing.

---

## Live end-to-end through real HTTP, real EasyOCR, real EXAONE

`uvicorn --factory ilgeojwo.web.wire:app`, then `curl -F` with each fixture. Both
lenses returned `status: ok` and both rows persisted. This is the first exercise of
`wire.py` and `build_ocr_engine` — every unit test injects fakes.

### Document lens

`deadline: 2026-10-05` (exact), `amount: "60,000원"`, sender *"Seoul Immigration
Service Foreigner Office"*, and an action sentence that reads correctly — all
recovered from OCR that had written 연장히가, 신청서클, 남부기한 and `60,00o원`.

### Label lens — the result that justifies the whole architecture

The model was asked only to transcribe. Here is what it produced:

```
rendered:   이부프로펜          슈도에페드린염산염        클로르페니라민말레산염
easyocr:    이부프로편          수도에페드린염산염        킬로르페니라민말레산염
EXAONE:     "ibuprofen"        "cetirizine hydrochloride"  "ketofenilamine maleate"
            correct            WRONG DRUG                  INVENTED
```

`슈도에페드린` is pseudoephedrine, a decongestant. EXAONE called it **cetirizine**,
which is an antihistamine — a different drug in a different class.
`클로르페니라민` became **"ketofenilamine"**, which is not a drug at all. Two of
three ingredients wrong, stated confidently.

All three warnings fired anyway:

| rule | found_in | approximate | why it survived |
|---|---|---|---|
| `nsaid` | `ingredients` | no | the model corrected the OCR's 이부프로편 |
| `decongestant` | **`ocr_text`** | no | "cetirizine" matched nothing; raw 에페드린 did |
| `sedating_antihistamine` | **`ocr_text`** | yes | "ketofenilamine" matched nothing; fuzzy caught 클로르페니라민 |

**Two of the three warnings existed only because the matcher screens the raw OCR
text as well as the model's output.** The natural design — trust the extracted
ingredient list — would have dropped the decongestant and the antihistamine, and
replaced one of them with a wrong drug name on screen. Spec §5.2 was written as a
precaution. It turns out to be load-bearing.

### A defect this run exposed: the dosage

Source: `1일 3회 1정 식후 복용` — one tablet, **three times** a day, after meals.
EXAONE returned: *"Take 1 tablet once daily after meals."*

A wrong frequency on medication is not an acceptable translation error, and she has
no way to check an English sentence against a Korean box. The card now carries
`dosage_ko` — the dosage line verbatim — shown **above** the translation, with the
translation explicitly marked as untrustworthy. The Korean is what she shows the
pharmacist.

---

## A plausible fix that made things worse

The final review noted, correctly, that Review Focus 2 (rotated photos) was never
measured, that the rotation test fed isolated jamo to a fake while EasyOCR decodes
precomposed syllables, and that `detail=0` discarded per-box confidence — the one
available discriminator between real text and garbage. Both observations were right.
The remedy I inferred from them was wrong, and the golden suite said so.

Enabling `rotation_info=[90, 180, 270]` and filtering boxes by confidence:

| configuration | the chlorpheniramine line | confidence |
|---|---|---|
| `paragraph=False`, no rotation | `킬로르페니라민말레산염 2mg` | **0.37** |
| `paragraph=False`, `rotation_info` | `[` | **0.53** |

On an **upright** image, offering EasyOCR rotations made it choose a wrong
orientation for one box and return a single bracket — with *higher* confidence than
the correct reading it replaced. The `sedating_antihistamine` warning disappeared
from the cold-medicine fixture, and the golden test caught it.

The second lesson is sharper: **confidence does not separate real Korean from OCR
garbage here.** The correct ingredient line scored 0.37; the garbage scored 0.53.
Any floor that drops the garbage also drops the ingredient. So the floor is now
0.05 — enough to remove degenerate boxes only — and a shape check discards
single-character non-word boxes, which is what `[` actually is.

Review Focus 2 therefore remains **unmeasured**, and honestly so. Rotation handling
has to be earned with a genuinely rotated fixture, not assumed from a plausible
argument. Turning it on without one cost a high-severity warning.
