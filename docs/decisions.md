# Decisions and their costs

Every judgement call made while building this, with what it costs if wrong,
and every review finding that was acted on. Extracted from the build ledger
so the reasoning survives in git rather than only in a scratch directory.

## Judgement calls (18)

- Setup: Ruling: used a branch, not a git worktree — brand-new repo with nothing on main to protect, and worktree ceremony costs wall-clock against a 2026-10-05 06:59 UTC deadline — cost if wrong: main is untouched either way, so none.

- Pre-flight: Ruling: T10 has extract/ import risk/ (extract_label calls match_risks), which strains spec §4.3's claim that extract/ "never makes a judgement" — a cleaner boundary would have web/ call match_risks and attach the warnings. Keeping the plan's arrangement: if the caller is responsible for screening, a future caller can forget, and forgetting means every warning silently disappears — the exact failure spec §5.2 exists to make impossible. Composing it inside extract_label makes the screening unskippable. extract/ still never decides; it only carries what risk/ decided. Cost if wrong: extract/ cannot be reused without risk/ — a one-file refactor.

- Task 0: Ruling: step 1 (message her for laptop specs, photos, and her doctor's instructions) is a human action I cannot perform — surfaced to the user instead. Not blocking T1–T10. T11 (golden fixtures) and T12 step 3 (her real rule list) cannot complete without it.

- Task 0: Ruling: ran the spike concurrently with T1–T5 instead of strictly gating on it — the gate exists to stop work being built on a broken stack, but ocr/ and the LLM sit behind protocols (T3, T4), so T1–T5 are byte-identical whichever engine wins. Cost if wrong: if both PaddleOCR-VL and EasyOCR fail outright, only T3's PaddleOcrVlEngine class body changes, which is one isolated class.

- Task 1: Ruling: also committed .gitignore, uv.lock and dropped pyproject's [project.scripts] entry, none of which the brief's add-list named — uv_build resolves that entry to ilgeojwo:main, which does not exist and would break the build, and an uncommitted lockfile makes her install unreproducible. Cost if wrong: none; no production behaviour touched.

- Task 0: steps 3-5 run with a RENDERED Korean document (/tmp/ilgeojwo/synthetic_doc.png, AppleSDGothicNeo) instead of her photos, which have not arrived. Ruling: a synthetic image validates that the stack loads and returns Korean on this M2, but NOT robustness on real phone photos (glare, skew, curved packaging) — that remains unvalidated until T11. Cost if wrong: PaddleOCR-VL could pass clean renders and fail real photos, which would surface at T11 and force the EasyOCR fallback late.

- Task 3: Ruling: did not `git rm scripts/spike_ocr.py` as step 5 says — the spike is still running against that file, and it was never committed, so there is nothing to remove from git. Deleting the untracked file once findings are recorded achieves the same end. Cost if wrong: none.

- Task 6: Ruling: step 5's "run the real app once against a real photo" is deferred until the Task 0 spike confirms PaddleOCR-VL works — the fast suite (8/8) proves the HTTP layer against injected fakes, which is what this task owns. Cost if wrong: a wiring bug between the real engine and create_app would surface at the first live run instead of now.

- Task 0: Ruling: kept PaddleOCR-VL as the default engine despite its weights download stalling here. Measured blob throughput on this link is 173 KB/s, so model.safetensors (1917255968 bytes) needs ~3h — but that is THIS connection, not the project: she is on Korean broadband, where the same file lands in under a minute. Swapping to a weaker OCR engine because my own link is slow would degrade the tool for the only person who will use it. Download left running in the background; T8-T10 need no OCR weights, so nothing is blocked. If the weights have not landed by the 2026-10-04 06:00 UTC cut line, EasyOCR becomes the configured engine then — a one-class change behind the existing OcrEngine protocol. Cost if wrong: the live end-to-end run and T11 golden tests slip to the far side of the cut line, and real-photo OCR quality stays unverified.

- Task 7: Ruling: step 5's offline check was verified by construction, not by switching WiFi off — every test injects a FakeEngine/FakeLlm, the only socket in the suite is 127.0.0.1:1 (deliberately refused), and the suite completes in 0.49s, which no real network call allows. Disabling WiFi would also have killed the in-flight 1.78 GB weights download. Cost if wrong: an accidental outbound call hidden in a dependency would go unnoticed until her first offline use.

- Task 8: Ruling: added a `_note` key to data/risk_rules.json marking the four rule groups PROVISIONAL — they are my inference from "pulmonary condition", not her doctor's instructions, and a medical rule file that does not say so invites being trusted more than it deserves. Cost if wrong: none; load_rules ignores unknown keys.

- Final: Ruling: I9/I10's return-shape change (distinguishing "no risk found" from "nothing screenable") NOT made in risk/. Instead the practical hole it named — a front-panel brand photo looking "cleared" — is closed with brand patterns (부루펜, 게보린, 사리돈, 판콜), and the "nothing screenable" signal stays where the user sees it, in T10's zero-ingredient notice (spec §3.2). Cost if wrong: a caller other than the web layer could misread [] as "safe".

- Task 10: Ruling: load_rules is called once in create_app rather than per request, so a malformed rule file fails loudly at startup instead of silently yielding zero warnings on her first real scan. Cost if wrong: editing risk_rules.json needs a restart to take effect.

- Task 10: Ruling: step 5 (photograph a real medicine box) deferred — EasyOCR's model download is still in flight and her photos have not arrived. The HTTP path is proven against injected fakes (10/10). Cost if wrong: a real-engine wiring bug surfaces at first live use.

- Task 11: harness committed, task NOT complete. Ruling: adapted to the user's choice of "real photos, gitignored" — her photos and their expectations are excluded by .gitignore (*.private.*), and four committed `*.synthetic.png` renders keep the suite runnable for anyone who clones. Only the private fixtures say anything about robustness on real phone photos; the synthetic ones are a clean-render proxy and the test module says so. Cost if wrong: a cloner's green golden run proves less than it appears to, which the docstring states outright.

- Task 11: Ruling: RE-GRADED the reviewer's M2 ("no fuzzy tier") from Minor to a must-fix, against my own earlier acceptance of Minor. Justification is a measurement, not a preference: on the cold-medicine fixture EasyOCR returned 이부프로편 for 이부프로펜 and 킬로르페니라민 for 클로르페니라민, and two of three warnings — including the high-severity NSAID — were found ONLY by the single-substitution tier. Exact matching would have shown a clean card for a box containing ibuprofen. This fixture's golden test failed before the tier and passes after it. Cost if wrong: approximate matches are extra warnings she must read; they are labelled POSSIBLE and an exact hit always outranks them.

- Final: Ruling: the live run exposed a dosage mistranslation — EXAONE rendered "1일 3회 1정 식후 복용" (three times a day) as "Take 1 tablet once daily". Fixed by carrying dosage_ko verbatim and rendering it ABOVE the translation with the translation marked untrustworthy, rather than by trying to make the model more accurate. A 2.4B model will keep making this class of error; the fix is to stop presenting its output as authoritative. Cost if wrong: two dosage rows on the card instead of one. Suite 279 -> 283. Evidence for spec §5.2, from the live run: EXAONE mistranslated 슈도에페드린 (pseudoephedrine) as "cetirizine hydrochloride" — a different drug in a different class — and 클로르페니라민 as the non-existent "ketofenilamine maleate". Two of three warnings fired ONLY via raw-OCR-text screening. The precaution is load-bearing, not theoretical.

- Final: Ruling: PDF input (spec §3.1 says "photo or PDF page") is REFUSED with a message telling her to photograph the page, not implemented. Implementing it needs another dependency and a rendering path, and university PDFs can be screenshotted. Cost if wrong: she must take one extra step for PDF correspondence. Named in the post's limitations.

## Review findings fixed (29)

- Final: fixed C1 full-width Latin (NFC -> NFKC) — test_full_width_latin_folds_to_ascii RED->GREEN

- Final: fixed C2 hyphen/soft-hyphen/middle-dot at OCR line break — test_breaks_and_invisibles_never_hide_an_ingredient_name (12 params) RED->GREEN. NOTE: the pre-existing Review Focus 3 test was green only because its assertion called .replace('-','') on normalize's OUTPUT, performing the work the implementation did not. My plan authored that test. The reviewer caught it; I would not have. This is the single clearest argument for the review gate.

- Final: fixed C3 zero-width characters (ZWSP/ZWNJ/WJ/BOM not matched by \s) RED->GREEN

- Final: fixed C4 severity unvalidated + unknown severity sorted BELOW low — now rejected at load, and the in-matcher default sorts FIRST RED->GREEN

- Final: fixed C5 empty rule list silently disabled all warnings; match_ko as a bare string became one pattern per character RED->GREEN

- Final: fixed C6 codeine class entirely absent — added opioid_antitussive RED->GREEN

- Final: fixed I7 messages asserted "Contains an NSAID" on a box whose precautions paragraph merely names ibuprofen — reworded to "is named on this packaging" RED->GREEN

- Final: fixed I8/I9 matched and found_in now report every hit and both sources RED->GREEN

- Final: fixed I11/I12 loader validation (empty/blank message, duplicate id, dict patterns, whitespace-only always-fire pattern, non-string id) with errors that name the offending rule RED->GREEN

- Final: fixed I13 match_risks raised TypeError on None — a crash in the safety module means a 500 and zero warnings, i.e. it failed unsafe RED->GREEN

- Final: fixed I14 coverage — pyrazolones, sulfites, topical/nasal decongestants, ophthalmic beta-blockers, more NSAIDs and antihistamines, Korean brand names RED->GREEN

- Final: fixed I15 §5.2 was proved by one example — now every shipped pattern is parametrised through match_risks (108 cases) RED->GREEN

- Final: fixed I16 purity test grepped the module's own source text for "urllib", which was self-referential and blind to transitive imports — replaced with an AST import-graph assertion RED->GREEN

- Final: fixed M1 " ".join fused ["에","페드린"] into a phantom 에페드린 — joins on \x00 RED->GREEN

- Final: fixed M2 README claimed the false-negative guarantee unconditionally — now states its bound (listed names only, no fuzzy tier, OCR substitution defeats it, a match is not proof of containment)

- Final: fixed C1/C2/I6 — the card showed model-invented drug names as fact. The measured live run had EXAONE render pseudoephedrine as "cetirizine hydrochloride" and invent "ketofenilamine maleate"; both appeared in the Ingredients row unhedged, and ingredients_found came from model truthiness so a model inventing three excipients bypassed spec §3.2's zero-ingredient notice. Model is now asked for ingredients_ko verbatim; only Korean present in the scan is shown; everything claimed is still screened. Same grounding applied to dosage_ko and deadline_text. RED->GREEN. This was the identical bug I had already fixed for dosage, one row above it on the same card — I fixed the instance and not the class.

- Final: fixed C3 — readability gate returned before the matcher ran, so a blister foil reading exactly 이부프로펜 200mg (5 syllables, under min_hangul) was reported unreadable and never screened. Label scans now always screened. RED->GREEN.

- Final: fixed C4 — setup.sh warmed PaddleOCR-VL (the unusable engine) and not EasyOCR, so a clean setup downloaded 1.78 GB of dead weight, left the ~100 MB EasyOCR cache unfetched, and broke the offline promise on her first pharmacy visit. Now warms the CONFIGURED engine and polls Ollama instead of sleep 3. RED->GREEN.

- Final: fixed C5/I9/I12 — every OCR, filesystem and timeout failure reached her as "Something went wrong." Now 503/413/415 with the component named and the command to run; failed scans no longer orphan a copy of her document in uploads/. RED->GREEN.

- Final: fixed C6/C7 — fuzzy tier too loud AND too quiet. 이산화황 is one substitution from 이산화티타늄/이산화탄소/이산화규소 (on a large share of Korean tablets, drinks, snacks) and "sulfate" one from "sulfite", so ordinary labels fired a sulfite warning; meanwhile the length floor excluded 코데인 and 티몰롤, short AND high-severity AND fragile to the ㅔ/ㅐ misread. Decision moved into the rule file as per-pattern no_fuzzy/force_fuzzy, validated against the rule's own patterns. RED->GREEN.

- Final: fixed I1 — 살리실산·메틸파라벤 fused into 살리실산메틸 and fired a high-severity NSAID warning marked EXACT, so the POSSIBLE hedge never showed. Three tiers now: boundary-preserving exact, fused exact (hedged), bounded fuzzy. RED->GREEN.

- Final: fixed I2 — the rotation test fed isolated jamo to a fake, but EasyOCR decodes precomposed syllables, so it passed for the wrong reason and Review Focus 2 was untested. Engine now uses detail=1 with a per-box confidence floor and rotation_info=[90,180,270]; keep_confident is pure and tested. RED->GREEN.

- Final: fixed I4 — deadline_text was stored, asserted and never rendered, so a notice reading 10월 5일까지 showed only "By: No date found". RED->GREEN.

- Final: fixed I5 — parse_korean_date took the FIRST date, so 접수기간 A~B returned the opening date and 제2026-10-05호 parsed a reference number as a deadline. Now returns the last plausible date, rejects reference numbers, and bounds the year. RED->GREEN.

- Final: fixed I7 — added the issue==deadline guard; Review Focus 1's only defence was prompt wording from a model measured turning "three times a day" into "once daily".

- Final: fixed I8 — /scans was correct, sorted and unreachable; the page never fetched it. Spec §3.1's deadline list is the feature. RED->GREEN.

- Final: fixed I10 — /scans on 0.0.0.0 returned the full OCR text of every document to any unauthenticated request on the subnet, contradicting §1's success criterion. `make run` now mints a pairing token carried in the QR link. RED->GREEN.

- Final: fixed I11 — blocking OCR and a 180s urllib call ran on the event loop, so the page itself froze for the whole scan. Handler is now sync (threadpool) and the lazy Reader build is locked so two concurrent first requests cannot double the memory.

- Final: fixed I13 — tests/golden/expected/ was allow-by-default; now deny-by-default like fixtures/. Added LICENSE (README claimed MIT with no file) and corrected the README footprint table, which documented the engine that does not run.

## Known limitations, deliberately deferred (10)

- Task 6: minor (deferred): starlette TestClient emits StarletteDeprecationWarning ("install httpx2 instead"). Third-party, no effect on correctness; swapping the test HTTP client mid-build risks churn for cosmetics.

- Final: minor (deferred): M3 ordering test coupled to the shipped data file — partially addressed (now asserts sortedness, not an exact list).

- Final: minor (deferred): M4 `profile` is read and discarded; no rule-file version field.

- Final: minor (deferred): M5 the PROVISIONAL _note never reaches her in the UI.

- Final: minor (deferred): M2 no fuzzy/edit-distance tier for single-glyph OCR substitution (이부프로펜 -> 이부프로팬). Documented in the README instead.

- Final: minor (deferred): uploads/ is never pruned.

- Final: minor (deferred): no Windows path for setup.sh/make.

- Final: minor (deferred): rule-file `profile` still read and discarded; no version field.

- Final: minor (deferred): PROVISIONAL rule-file note still not surfaced in the UI.

- Final: minor (deferred): starlette/httpx deprecation warning.

## Other notes

- Task 0: licences VERIFIED from the artifacts, not assumed (spec §4.2): - EXAONE 3.5 2.4B: "EXAONE AI Model License Agreement 1.1 - NC" (ollama show --license) — non-commercial, as the spec anticipated. - PaddleOCR-VL-1.6: apache-2.0 (HF model card metadata).

- Task 7: STOPPED at step 6's `gh repo create ilgeojwo --public --push`. Publishing a public repository is an outward-facing, hard-to-reverse action, so it needs the user's explicit go-ahead rather than my judgement. Committed locally instead; asked the user. Not blocking T8-T10.

- Task 11: step 3 (run and verify) BLOCKED on EasyOCR's model download (43 MB of ~100 MB) and on her photos. Not calling task-done: the completion contract needs the task's own tests to have run and passed.

