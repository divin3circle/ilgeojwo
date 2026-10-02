# 읽어줘 (Ilgeojwo) — Design

**Date:** 2026-10-02
**Context:** DEV.to Hacktoberfest Weekend Challenge 2026 — "Build something with open-source AI at its core" / "Ship something that solves a real problem for a friend or someone you love."
**Submissions close:** 2026-10-05, 06:59 UTC.

---

## 1. Intent

### Who this is for

The author's sister, a Masters student living in South Korea. She reads little
Korean. She has a pulmonary condition.

### The problem, as stated

Two frictions, both of the form *"a Korean thing is in front of me and I cannot
tell what it means for me."*

1. **Official paperwork.** Immigration and ARC correspondence, university admin
   forms, bank letters, lease documents, utility bills. Dense formal Korean. She
   cannot tell what is being asked of her, what it costs, or by when. Missing a
   deadline has real consequences for a visa holder.

2. **Medicine and product labels.** Korean over-the-counter cold and pain
   medication commonly contains NSAIDs and decongestants. For someone with a
   respiratory condition these are not neutral. She is handed a box in a pharmacy
   and cannot read the active ingredients or the dosage.

### Success criteria

- She uses it, in Korea, before the submission deadline, and says whether it
  helped. Her feedback is recorded and quoted in the post.
- It runs with the network switched off.
- Her passport number, address, condition, and medication list never leave her
  laptop.
- It correctly reads and explains at least one real document and one real
  medicine box that she supplies.

### Assumptions requiring confirmation at build time

- Her laptop has roughly 4 GB free RAM and 5 GB free disk. If not, the model
  configuration drops to the 1.5B tier.
- She is reachable for a walkthrough and for feedback inside the submission
  window, accounting for the time difference.

---

## 2. Non-goals

Explicitly out of scope. These are cut to protect the two things that matter.

- Accounts, authentication, multi-user support, cloud sync.
- A chat interface. The tool answers one question per photo.
- Handwriting recognition.
- Spoken Korean practice or conversation.
- General-purpose translation of arbitrary text.
- Air quality or any other external data feed.
- Any diagnosis, dosage recommendation, or medical advice. See section 5.

---

## 3. Functional specification

One camera. Two lenses. The lens is chosen by the user with a toggle, not
inferred, because a wrong inference in the medicine path is a safety problem.

### 3.1 Document lens

Input: a photo or PDF page of a Korean document.

Output, one card:

| Field | Behaviour when absent |
|---|---|
| Document type | "Unidentified document" |
| Sender / issuing body | "Unknown sender" |
| What you must do | "No clear action found" |
| Deadline | **"No date found"** — never inferred, never guessed |
| Amount payable | "No amount found" |
| Where to go / how to act | omitted |
| Original Korean text | always shown, verbatim |

Cards are saved and listed, soonest deadline first. Undated cards sort last.

### 3.2 Label lens

Input: a photo of a medicine box, blister pack, insert, or food packaging.

Output, one card:

| Field | Behaviour when absent |
|---|---|
| Product name | "Unidentified product" |
| Kind (medicine / food) | "Unknown" |
| Active ingredients | **explicit failure notice**, see below |
| Dosage as printed | "Dosage not found — ask the pharmacist" |
| Risk flags | rendered from the matcher, see section 5 |
| Original Korean text | always shown, verbatim |

If zero ingredients are extracted, the card does not render as a clean result. It
renders a visible failure: *"Could not identify the ingredients in this photo. Do
not rely on this. Show the box to the pharmacist."*

---

## 4. Architecture

### 4.1 Pipeline

```
photo
  │
  ├─> PaddleOCR-VL-1.6 (0.9B, local) ──> Korean text  ─────────────┐
  │                                            │                   │
  │                                            v                   │
  │                              local LLM (EXAONE 3.5 2.4B)       │
  │                              extraction only, emits JSON       │
  │                                            │                   │
  │                                            v                   v
  │                                   extracted fields      raw OCR text
  │                                            │                   │
  │                                            └────────┬──────────┘
  │                                                     v
  │                                          risk matcher (pure logic,
  │                                          runs on BOTH inputs)
  │                                                     │
  └─────────────────────────────────────────────────────v
                                                   rendered card
```

### 4.2 Components

| Concern | Choice | Why |
|---|---|---|
| Reading Korean off an image | PaddleOCR-VL-1.6, 0.9B, Apache 2.0 | Tops OmniDocBench v1.6 at 96.34%; documented as robust to screen photography, warped pages, uneven lighting — i.e. phone photos. Official Apple Silicon support. Runs via `transformers>=5.0` without the PaddlePaddle framework. |
| Understanding and explaining | EXAONE 3.5 2.4B Instruct, via Ollama (`exaone3.5`) | Purpose-built bilingual Korean–English. Official first-party GGUF. 4-bit fits in ~1.6 GB. |
| Weaker-laptop fallback | HyperCLOVAX-SEED-Text-Instruct-1.5B (Naver), via Ollama | One config line. Smaller, and a more permissive licence. |
| Lighter OCR fallback | PaddleOCR PP-OCRv5 Korean recogniser, or EasyOCR | If the VLM is too heavy on her machine. CPU-friendly, well-trodden. |
| Serving | FastAPI, one HTML page | No build step. `<input type="file" capture="environment">` gives the phone camera for free. |
| Storage | SQLite | Local file. Nothing to administer. |
| Risk rules | A hand-written JSON file in the repo | Human-readable, reviewable, version-controlled, editable by her. |

**Resident memory budget:** ~1 GB OCR + ~1.6 GB LLM at 4-bit ≈ **under 3 GB**, both
loaded at once.

**Licensing, to be stated honestly in the post:** PaddleOCR-VL is Apache 2.0.
EXAONE 3.5 ships under LG's own model licence, which restricts commercial use —
acceptable for a personal tool, and the exact terms will be read and quoted
before release. HyperCLOVAX-SEED's licence is the more permissive of the two and
is the recommended choice if anyone wants to build on this commercially. Each
licence is verified at build time, not assumed.

### 4.3 Module boundaries

Each of these is independently testable and knows nothing of the others' internals.

- `ocr/` — image in, Korean text out. No knowledge of lenses or risk.
- `extract/` — Korean text plus a lens, out comes validated structured JSON.
  Owns the prompts and the schema. Never makes a judgement.
- `risk/` — ingredient names and raw text in, warnings out. Pure functions, no
  I/O, no model. The safety-critical module, and the smallest.
- `store/` — persistence of cards.
- `web/` — HTTP and one page. Renders what it is given.

---

## 5. Safety design

**The model reads. A hand-written rule decides.**

This is the central decision of the project. A 2.4B model that invents a drug
interaction could cause real harm to a person with a respiratory condition. So
the model is never permitted to make the safety call.

### 5.1 Division of responsibility

- The LLM's only job in the label lens is **transcription and extraction**:
  pulling ingredient names and the printed dosage out of OCR text. It is not
  asked whether something is safe, and its output is never used as a judgement.
- Every warning is produced by `risk/`, a deterministic matcher over a curated
  JSON rule file.

### 5.2 The matcher runs on raw OCR text as well as model output

A warning is raised if a risk pattern appears in **either** the LLM's extracted
ingredient list **or** the raw OCR text. This makes the failure direction safe:
if the model misses an ingredient the raw text still catches it. A model failure
can produce a false positive. It cannot silently produce a false negative.

### 5.3 Rule file shape

```json
{
  "profile": "respiratory",
  "rules": [
    {
      "id": "nsaid",
      "severity": "high",
      "match_ko": ["이부프로펜", "아스피린", "나프록센", "덱시부프로펜"],
      "match_en": ["ibuprofen", "aspirin", "naproxen", "dexibuprofen"],
      "message_en": "Contains an NSAID. NSAIDs can trigger breathing problems in some people with asthma and related conditions. Show this box to the pharmacist and ask whether acetaminophen (아세트아미노펜) is suitable for you.",
      "source": "GINA 2025 report, NSAID-exacerbated respiratory disease; cross-checked against the Korean product insert"
    }
  ]
}
```

Initial rule groups: NSAIDs, decongestants (pseudoephedrine, phenylephrine),
non-selective beta-blockers including ophthalmic ones, and sedating
antihistamines. Every rule carries a citation. The list is deliberately small,
conservative, and reviewed by a human before shipping.

Matching normalises Unicode (NFC) and strips whitespace, because Korean OCR
output spacing is unreliable.

### 5.4 What the tool says about itself

Permanently visible in the label lens: this is a reading aid, not medical advice;
it does not know her full history; confirm with the pharmacist or her doctor. The
tool flags and defers. It never recommends.

---

## 6. Data model

`scans` — `id`, `created_at`, `lens`, `image_path`, `ocr_text`,
`extracted_json`, `status` (`ok` | `partial` | `unreadable`).

Lens-specific fields live inside `extracted_json` rather than in columns, because
the two lenses have little overlap and the shape will move during the build.

Deadlines are stored as an ISO date **or null**. There is no "probably around"
representation, by design.

---

## 7. Error handling

The governing rule: **degrade visibly, never invent.**

| Failure | Behaviour |
|---|---|
| OCR returns nothing or gibberish | Card marked `unreadable`. "Couldn't read this — try more light, a flatter angle, or move closer." No guessing. |
| LLM emits invalid JSON | One retry with a stricter prompt. On second failure, show the Korean text with a plain rendering of it and mark the card `partial`. This is a degradation path, not the general-purpose translation ruled out in section 2. |
| A field is missing | Render the explicit absence string from section 3. Never fill a gap. |
| Date unparseable | "No date found." Never infer a deadline. |
| Zero ingredients in label lens | Visible safety failure notice, not a clean card. |
| Model or weights missing | Clear setup error naming the missing component and the command to fix it. |

---

## 8. Testing strategy

- **`risk/` unit tests** — the safety-critical module gets the most attention.
  Korean and English ingredient variants, OCR spacing noise, NFC/NFD forms,
  negative cases that must *not* fire, and a test asserting that a pattern
  present only in raw OCR text still raises its warning.
- **Korean date parsing unit tests** — `2026년 10월 5일`, `2026.10.05`,
  `2026-10-05`, and malformed input that must yield null rather than a date.
- **Golden-file extraction tests** — fixture images of real Korean documents and
  medicine boxes with hand-written expected fields. Comparison is exact on
  deadline, amount, and the set of ingredients; case- and whitespace-insensitive
  substring match on free-text fields such as sender and action. Free text is
  allowed to vary in wording; the facts are not.
- **A "never invents a deadline" property test** — no fixture lacking a date may
  ever produce one.
- **Offline test** — the suite runs with networking disabled and must pass.

---

## 9. Delivery

The product is her laptop. Her phone is a client on her own home network.

- `./setup.sh` — pulls the Ollama model, installs Python dependencies, fetches
  the OCR weights. Idempotent.
- `make run` — serves on the LAN and prints both the URL and a **QR code**, so
  she points her phone camera at her laptop screen once and is in.
- Flow in practice: she photographs a letter with her phone in the hallway; her
  laptop in the next room reads it; the answer appears on her phone.
- Her feedback is captured in writing and quoted in the submission post.

Render is **not** on the critical path. If the build lands early, a public demo
deployment is added as a clearly-labelled "try it yourself" for readers, which
also qualifies for that prize category. It is never a dependency of delivery.

---

## 10. The submission post

Writing quality is the most heavily weighted judging criterion, so the post is a
deliverable, not an afterthought. Required sections: What I Built, Demo, Code,
How I Built It, Why Open Innovation Matters.

The argument of the "Why Open Innovation Matters" section, which must be true
rather than decorative:

1. **The right model for this problem is Korean and open.** EXAONE and
   HyperCLOVA X SEED are built by LG and Naver for Korean. They are not available
   through any closed API at any price. Open weights are the only route to them.
2. **The data is medical and governmental.** Her condition, her medication, her
   passport number, her address. "It never leaves her laptop" is the feature, not
   a footnote.
3. **It works with the network off** — in a pharmacy, in a government office, in
   a basement.
4. **The model is swappable.** Her laptop is weaker than the author's, so the
   configuration drops from 2.4B to 1.5B by changing one line. That is not
   possible when the model is someone else's endpoint.
5. **It costs nothing to run forever**, which matters for a student.

---

## 11. Risks

| Risk | Mitigation |
|---|---|
| `transformers>=5.0` is new; dependency conflicts likely | Pin versions; isolated venv via `uv`; lighter PP-OCRv5 fallback already specified |
| First-run weight downloads are large on a 48 GB-free disk | Download once, measure, document the footprint in the README |
| Her laptop is weaker than assumed | 1.5B tier is a config change, designed in from the start |
| Glossy, curved medicine boxes defeat OCR | PaddleOCR-VL is specifically reported strong here; failure path is an honest "unreadable", which is acceptable behaviour |
| Time-zone coordination for delivery and feedback | Agree a window with her at the start of the build, not at the end |
| Scope overrun against a 2026-10-05 06:59 UTC deadline | The cut line in section 12 |

---

## 12. Staging and the cut line

0. **Spike (30–60 min, gating).** One real Korean image through PaddleOCR-VL and
   EXAONE on the author's M2. Confirms the whole technical premise before any
   product code exists. If this fails, the stack changes before anything is built.
1. Document lens, end to end, tested.
2. Label lens and the risk matcher, tested.
3. Delivery to her laptop; capture her feedback.
4. The post.
5. *Stretch only:* public demo deployment.

**The cut line: if the document lens is not solid and tested by 2026-10-04 06:00
UTC, stage 2 is abandoned and the project ships as the document lens alone.**
That leaves roughly 25 hours for delivery, feedback, and the post. The post is
complete and honest either way. Nothing half-finished is submitted. A smaller
working tool beats a larger broken one, and the failure mode is chosen
deliberately rather than discovered at hour 58.
