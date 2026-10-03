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

Seven fixes, each with a test that failed first. The suite went from 73 to 279.

### Then I measured the OCR, and the finding we both dismissed was the dangerous one

The reviewer listed one more thing, graded **Minor**: there is no fuzzy matching,
so if OCR misreads a syllable the warning does not fire. I read that, agreed it
was a reasonable v1 boundary, wrote it in the README as a known limitation, and
moved on. So did the reviewer. Two careful readers, same conclusion.

Then the OCR finished downloading and I ran it on a rendered Korean document whose
exact contents I knew.

```
rendered:  체류기간 연장허가 … 신청서를 … 납부금액: 60,000원
easyocr:   체류기간 연장히가 … 신청서클 … 남부금액: 60,00o원
```

허→히. 를→클. 납→남. Three substituted syllables, on a clean 34-point render with
no glare, no skew and no curvature. Not a photograph. The easiest input this tool
will ever see.

So I pointed the matcher at the cold-medicine fixture and printed what it actually
found:

```
rendered:  이부프로펜 200mg      슈도에페드린염산염 30mg      클로르페니라민말레산염 2mg
easyocr:   이부프로편 2OOmg      수도에페드린염산염 3Omg      킬로르페니라민말레산염 2mg
                  ^ 펜→편            ^ 슈→수                      ^ 클→킬

[high  ] nsaid                   APPROXIMATE  matched=('이부프로펜',)
[medium] decongestant            exact        matched=('에페드린',)
[low   ] sedating_antihistamine  APPROXIMATE  matched=('클로르페니라민',)
```

Two of the three warnings — **including the high-severity NSAID** — are found only
by a tier that did not exist. With exact matching alone, my sister photographs a
Korean cold medicine box containing ibuprofen, and the tool shows her a clean card.

That is the whole failure this project exists to prevent, and it was sitting behind
a limitation two people had independently signed off as acceptable.

The tier now runs only when nothing matches exactly, so a clean hit is never
downgraded to a guess. It requires a name of at least four characters, because one
changed character in a three-syllable name is too weak a signal to act on —
`코데인` stays exact-only while `인산코데인` and `디히드로코데인` carry it. And its
warnings say `POSSIBLE — the OCR may have misread this`, because a guess should
look like a guess.

It also introduced a false positive immediately. Ingredient-list entries are joined
with a null byte so that stripping whitespace cannot fuse two fragments into a drug
name — and the fuzzy tier cheerfully treated that null byte as the one substituted
character, matching `["에", "페드린"]` against `에페드린`. The test I had written
for the original fusion bug caught it on the first run.

There is a smaller lesson hiding in that output too. `decongestant` matched
*exactly*, despite `슈도에페드린염산염` being misread, because the rule list carries
the bare `에페드린` alongside the salt form — and the short form survived inside the
mangled long one. Listing both the drug and its salts buys redundancy for free.

**The review caught what I had assumed. The measurement caught what the reviewer
and I had both assumed.** Neither was sufficient alone, and the second one only
cost me running the thing and reading the output.

### And then the whole thing paid off at once

I started the real server, curled a medicine label at it, and read what came back.

The language model's only job was transcription. Here is what it transcribed:

```
rendered:   이부프로펜          슈도에페드린염산염          클로르페니라민말레산염
easyocr:    이부프로편          수도에페드린염산염          킬로르페니라민말레산염
EXAONE:     "ibuprofen"        "cetirizine hydrochloride"   "ketofenilamine maleate"
            correct             WRONG DRUG                   DOES NOT EXIST
```

`슈도에페드린` is pseudoephedrine, a decongestant. EXAONE called it
**cetirizine** — an antihistamine, a different drug in a different class, stated
with complete confidence. `클로르페니라민` became **"ketofenilamine,"** which is
not a drug at all.

Two of three ingredients wrong. And all three warnings fired:

| Warning | Found via | How |
|---|---|---|
| NSAID (high) | `ingredients` | the model *fixed* the OCR's 이부프로편 |
| Decongestant (medium) | **`ocr_text`** | "cetirizine" matched nothing; raw `에페드린` did |
| Sedating antihistamine (low) | **`ocr_text`**, approximate | "ketofenilamine" matched nothing; fuzzy caught `클로르페니라민` |

Read that middle row again. The model replaced a decongestant with an
antihistamine, and the decongestant warning still appeared — because the matcher
never trusted the model's list in the first place.

The obvious way to build this is to let the model extract ingredients and check
those. It is obvious, it is what I would have done without the spec in front of
me, and on this one real box it would have dropped two of three warnings and put a
wrong drug name on screen next to the one it kept.

Spec §5.2 — *"the matcher runs against the raw OCR text as well as the extracted
ingredient list"* — was written as a precaution against something I could not
demonstrate. It turns out to be the only reason this box got screened correctly.

### One more thing the same run broke

The box says `1일 3회 1정 식후 복용` — one tablet, **three times** a day.

EXAONE said: *"Take 1 tablet once daily after meals."*

A wrong frequency on medication is not an acceptable translation error, and she
has no way to check an English sentence against a Korean box. I did not try to
make the model more accurate, because a 2.4B model will keep doing this. I stopped
presenting its output as authoritative: the card now shows the Korean dosage line
**verbatim, above** the translation, with the translation explicitly marked as
untrustworthy. The Korean is the line she shows the pharmacist.

That is the pattern this whole project converged on, three times, from three
different directions: **let the model read, and never let it be the thing you
trust.**

### A third reader found that I had fixed the instance and not the class

I sent the finished branch to a fresh reviewer. It opened with the dosage fix I was
proudest of, and then pointed one row up the same card.

```
Ingredients:  ibuprofen, cetirizine hydrochloride, ketofenilamine maleate
Dosage, as printed:  1일 3회 1정 식후 복용      ← verbatim, hedged, trustworthy
Dosage, translated:  Take 1 tablet once daily  ← marked as possibly wrong
```

The dosage row had a Korean companion and a warning that the translation can be
wrong. The ingredient row — holding a drug that does not exist and another that is
the wrong class — had neither. I had fixed the *instance* of "model output
presented as fact" and walked straight past the *class*.

Worse, `ingredients_found` was `bool(ingredients)` — the truthiness of model
output. So a model that invents three plausible excipients from an unreadable photo
produced a clean card, and the "could not identify the ingredients" safety notice I
had written specifically for that case never fired. The notice was unreachable by
the exact failure it existed for.

Both are now grounded: the model is asked for the ingredient names verbatim in
Korean, only names actually present in the scanned text are shown to her, and
`ingredients_found` comes from that evidence rather than from the model having said
something. Everything the model claimed is still screened for risk — **screen
generously, display conservatively.**

The same reviewer found that `make run` served `/scans` — the full OCR text of
every document she has ever photographed — to any unauthenticated request on the
network. The server *has* to listen on `0.0.0.0` for her phone to reach it, and
Korean share-houses routinely put every unit on one subnet. A project whose central
claim is "her passport number never leaves her laptop" was handing it to the
building. There is now a one-time key in the QR link, and the page says so.

Three reviews, three different classes of mistake, and not one of them was
something I could have reasoned my way to from the chair.

### The last one is my favourite, because the fix was wrong

That reviewer also pointed out that I had never actually tested the rotated-photo
case, and that I was throwing away EasyOCR's per-box confidence scores — the one
signal that could tell real text from garbage. Both observations were correct.

So I turned on rotation handling and started filtering by confidence. Then I re-ran
the golden suite, and a warning had disappeared.

| configuration | the chlorpheniramine line | confidence |
|---|---|---|
| no rotation | `킬로르페니라민말레산염 2mg` | **0.37** |
| rotation enabled | `[` | **0.53** |

On an **upright** image, offering the engine rotations made it pick a wrong
orientation for one box and return a single bracket — at *higher* confidence than
the correct reading it destroyed. One of the three ingredients on the box stopped
being screened.

And confidence turned out to be worthless as a filter here: the correct line scored
0.37, the garbage scored 0.53. Any threshold that drops the garbage drops the drug.

So the rotation handling is gone, the confidence floor is low enough to only remove
empty boxes, and a shape check throws out single-character boxes — which is what
`[` actually is. Rotated photos remain untested, and the README says so, because
the alternative was a fix that cost a high-severity warning to buy a hypothesis.

Four times now: **reasoning proposed, measurement decided.**


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

- **The model mistranslates drug names.** Measured, not theoretical: pseudoephedrine
  became "cetirizine." The card now only shows ingredient names it can find in the
  scanned text, but the English translations beside them remain a convenience, not
  evidence.
- **PDFs are refused, not read.** University and bank mail arrives as PDF; the tool
  tells you to photograph or screenshot the page instead. A real gap, honestly named.
- **Anyone on your WiFi with the QR link can read every scan.** Mitigated with a
  one-time key, not solved. Treat the link as a password.
- **Fuzzy matching stops at one character.** Two substitutions in the same name,
  or a misread three-syllable name, still slip through. A clean result means
  "nothing on my list was found," never "this is safe" — and the card says that
  out loud rather than leaving her to infer it.
- **The rule file is provisional.** The groups are a conservative reading of
  "pulmonary condition," marked `PROVISIONAL` in the JSON. They include opioids
  and sulfites because a code reviewer told me to, not because a doctor did.
  Replacing them with her doctor's actual instructions is the next commit.
- **EXAONE 3.5 is licensed `NC`** — non-commercial. Fine for a tool built for one
  person. It is why this is not a product. For anyone wanting to build on this
  commercially, HyperCLOVA X SEED is the permissive alternative, and swapping to
  it is one environment variable.
- **The OCR has never seen a real phone photo.** Only clean renders — which
  already produced three substituted syllables. Real photographs will be worse,
  and I do not yet know by how much. That gap closes the first time she points her
  camera at something.
