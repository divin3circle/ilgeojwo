---
title: "읽어줘: I built my sister a Korean reader that never leaves her laptop"
published: false
tags: hacktoberfest, opensource, ai, python
---

> **DRAFT — two things still missing before this ships:** her feedback in her own
> words (Task 12 step 2) and the demo video (Task 12 step 4). Everything else is
> written against code that exists and tests that run.

## What I Built

My sister is doing a Masters in South Korea. She reads very little Korean, and
she has a pulmonary condition.

Two things kept going wrong for her, and they turn out to be the same problem
wearing different clothes.

The first is paperwork. Immigration letters, university forms, bank notices,
utility bills — dense formal Korean, arriving on paper, with deadlines attached.
She would photograph them and send them to me, and I would squint at them too.
For someone on a student visa, a missed date is not an inconvenience.

The second is worse, and I did not see it until I asked her what the doctor had
told her. Korean over-the-counter cold and pain medicine routinely contains
NSAIDs and decongestants. NSAIDs can trigger breathing problems in people with
asthma and related conditions. She stands in a pharmacy, is handed a box, and
cannot read the ingredients panel.

So: **읽어줘** — *ilgeojwo*, "read it to me." Point a phone camera at anything
Korean that has consequences. Two lenses, one engine.

**Document lens** gives her a card: what this is, who sent it, what she must do,
by when, how much, where to go — and the original Korean, verbatim, always.

**Label lens** gives her the product, the active ingredients as printed, the
dosage in English, and flags anything on a risk list she controls.

Everything runs on her own laptop. No API key, no account, no upload. Her
passport number, her address, her condition, her medication list — none of it
leaves the machine. It works with the WiFi switched off.

## Demo

*Pending: screen recording of a real immigration letter in document mode, a real
Korean cold medicine box in label mode showing a live warning, and then the same
scan again with WiFi disabled.*

## Code

{% embed https://github.com/divin3circle/ilgeojwo %}

## How I Built It

```
photo
  └─> OCR (local) ──> Korean text ────────────────────┐
                            │                         │
                            v                         │
                  local LLM: EXAONE 3.5 2.4B          │
                  extraction only, emits JSON         │
                            │                         v
                     extracted fields           raw OCR text
                            └──────────┬──────────────┘
                                       v
                          risk matcher (pure logic,
                          reads BOTH inputs)
                                       │
                                       v
                                 rendered card
```

- **Reading Korean**: EasyOCR, CPU-only, Korean + English.
- **Understanding it**: **EXAONE 3.5 2.4B Instruct** from LG AI Research, via
  Ollama. Bilingual Korean–English, 1.6 GB on disk at 4-bit.
- **Serving**: FastAPI, one HTML page, SQLite. `make run` prints a QR code; she
  scans it with her phone on her own WiFi and she is in. She photographs a letter
  in the hallway and her laptop in the next room reads it.

### The decision the whole project rests on

**The model reads. A hand-written rule decides.**

A 2.4-billion-parameter model that invents a drug interaction could hurt her. So
the language model is never allowed to make the safety call. On a medicine label
its entire job is transcription: pull the printed ingredient names and dosage out
of the OCR text. It is never asked whether something is safe.

Every warning comes from a deterministic matcher over a curated JSON file where
each rule carries a citation. And the matcher runs against **the raw OCR text as
well as** the model's extracted ingredient list:

```python
in_ingredients = _hits(rule, from_ingredients)
in_ocr         = _hits(rule, from_ocr)
if not (in_ingredients or in_ocr):
    continue
```

That `or` is the point. If the model misses an ingredient completely, the raw
text still raises the warning. A model failure can produce a false positive. It
cannot produce a *silent false negative* — and in a tool like this, those are not
symmetrical. An extra warning is an annoyance. A missing one is the whole failure.

### Then I had the module reviewed, and it was wrong seven ways

I had 73 passing tests and a docstring claiming no silent false negatives. I
handed the module to a fresh reviewer and asked it to break that claim.

It broke it seven times, each with a working input:

| What slipped through | Why |
|---|---|
| `ＩＢＵＰＲＯＦＥＮ` | Full-width Latin, routine on CJK packaging. I used NFC; it needed NFKC. |
| `이부-\n프로펜` | OCR hyphenates across a line break on a narrow panel. |
| `이부​프로펜` | Zero-width characters. `\s` does not match them. |
| `{"rules": []}` | An empty rule file silently disabled **every** warning. |
| `"match_ko": "이부프로펜"` | One missing `[` made a pattern per character, firing on any Korean text. |
| `"severity": "critical"` | Sorted *below* `low`. The worst warning, at the bottom of her card. |
| `디히드로코데인` | The entire codeine class was absent. Opioid respiratory depression in a lung patient is the most direct harm this tool exists to prevent. |

The one I want to dwell on is the hyphen, because it had a test, and the test was
green:

```python
assert normalize("ibu-\nprofen").replace("-", "") == normalize("ibuprofen")
```

Look at `.replace("-", "")`. The assertion strips the hyphen *outside* the
function under test. The test performed the work the implementation did not, then
passed, and told me the case was covered for as long as I cared to believe it. I
wrote that test myself, in the plan, specifically to cover that case.

A test you wrote to confirm a behaviour you assumed can launder the assumption
into a green checkmark. I would not have found it. A fresh reader did, in one
pass.

The reviewer also caught something subtler and arguably worse. My warnings said
*"Contains an NSAID."* Korean boxes list other drugs in their 주의사항
(precautions) paragraph — so a plain Tylenol box, whose only active ingredient is
acetaminophen, says `이부프로펜` on the back under "do not take with." My tool
fired a high-severity warning asserting it contained an NSAID. On the exact drug
the NSAID rule tells her to ask for instead.

That is not a false positive you can shrug at. That is how you teach someone to
stop reading warnings. Every message now says a name **is named on this
packaging**, shows her what matched, and tells her a match is not proof of
containment.

Seven fixes, each with a test that failed first. The suite went from 73 to 265.

## Why Open Innovation Matters

### 1. The right model for this problem is Korean, and it is only open

**EXAONE 3.5** is built by LG AI Research, bilingual Korean–English by design.
Naver's **HyperCLOVA X SEED** and Kakao's **Kanana** sit beside it. These models
are not available through OpenAI or Anthropic at any price. Open weights are not
a cheaper route to them — they are the *only* route.

The best tool for a person living in Korea was built in Korea, and I could use it
because the weights are open.

### 2. The data is medical and governmental

Her condition. Her medication list. Her passport number. Her address. Her ARC
number.

"It never leaves her laptop" is not a privacy footnote I added for the judges. It
is why the architecture is shaped the way it is. There is no endpoint to send
anything to. Her real document photos are not even in the repository — they are
test fixtures, gitignored, because an immigration letter identifies her even with
the passport number covered.

### 3. It works with the network off

In a pharmacy. In a government office. In a basement with no signal. The models
are on the disk.

### 4. When one model turned out to be broken, I swapped it in one line

I did not choose EasyOCR first. I chose **PaddleOCR-VL-1.6** — 0.9B parameters,
Apache 2.0, state of the art on OmniDocBench, documented as robust to exactly the
skewed, badly-lit phone photos this tool lives on.

It does not load. Its `trust_remote_code` modeling file calls
`ROPE_INIT_FUNCTIONS['default']`, and that key was removed in the transformers
5.0 major release — while the model card requires `transformers>=5.0.0` for that
very backend. I checked v5.0.0, v5.5.0 and v5.10.0. None of them have it. The
published path cannot work on any supported version.

Here is the part that matters. I could **read the failing line**. I could check
three upstream versions in thirty seconds. I could see that the fix meant writing
rope-initialisation maths by inference, decide that was not something to guess at
in a medical-adjacent tool, and swap engines:

```bash
ILGEOJWO_OCR_ENGINE=easyocr make run
```

The broken engine is still in the tree, still selectable, waiting for upstream.

With a closed API I would have had an opaque error and a support ticket. The
honest cost is real — EasyOCR's Korean accuracy is below a 0.9B VLM's, so her
extraction quality is lower than I planned. But "lower than planned" beats
"blocked indefinitely," and I only had that choice because every piece was
inspectable.

### 5. It costs nothing to run, forever

She is a student. There is no bill, no quota, no trial expiry, and no company
that can deprecate the thing she depends on to read her visa letters.

## What does not work

- **No fuzzy matching.** If OCR reads `이부프로펜` as `이부프로팬`, the warning
  does not fire. A clean result means "nothing on my list was found," never "this
  is safe," and the README says so.
- **The rule file is provisional.** The groups are a conservative reading of
  "pulmonary condition," marked `PROVISIONAL` in the JSON. They include opioids
  and sulfites because a code reviewer told me to, not because a doctor did.
  Replacing them with her doctor's actual instructions is the next commit.
- **EXAONE 3.5 is licensed `NC`** — non-commercial. Fine for a tool built for one
  person. It is why this is not a product. For anyone wanting to build on this
  commercially, HyperCLOVA X SEED is the permissive alternative, and swapping to
  it is one environment variable.
- **The OCR has never seen a real phone photo.** Only clean renders. That gap
  closes the first time she points her camera at something.
