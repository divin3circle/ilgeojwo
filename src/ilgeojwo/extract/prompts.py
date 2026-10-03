"""Prompts. The model transcribes and extracts; it never judges (spec §5.1)."""

DOCUMENT = """You are reading text that was scanned from a Korean document.
Extract only what is literally present. Do not add, infer, or assume anything.

The reader does not read Korean. Every value below marked "in English" MUST be
written in English. Never copy Korean into those fields.

Return a single JSON object with exactly these keys:
  doc_type      - what kind of document this is, in English
  sender        - the issuing office or company, in English
  action        - what the reader must do, in English, one sentence
  deadline_text - the deadline EXACTLY as written in Korean, or ""
  issued_text   - the issue date EXACTLY as written in Korean, or ""
  amount        - any amount payable as written, or ""
  location      - where to go or how to act, or ""

If a field is not present in the text, use "". Never guess.

Korean text:
{text}"""

DOCUMENT_RETRY = """Your previous reply was not usable: it was either not valid
JSON, or it left Korean in fields that must be English.

Reply with ONE valid JSON object and nothing else. No prose, no markdown fence.
Keys: doc_type, sender, action, deadline_text, issued_text, amount, location.

doc_type, sender and action MUST be written in English. Translate them. The
person reading this cannot read Korean at all, so Korean in those fields is
useless to them. Only deadline_text and issued_text stay in Korean, copied
exactly as printed.

Use "" for anything not present in the text.

Korean text:
{text}"""

LABEL = """You are reading text scanned from Korean product or medicine packaging.
Transcribe and list only what is literally printed. Do not interpret.

Return a single JSON object with exactly these keys:
  product_name - the product name in English, or ""
  kind         - "medicine" or "food", or ""
  ingredients_ko - a list of active ingredient names EXACTLY as printed in
                   Korean, copied character for character, or []
  ingredients  - the same list translated to English, same order, or []
  dosage       - the dosage instructions in English, or ""
  dosage_ko    - the dosage line EXACTLY as written in Korean, copied
                 character for character, or ""

List every active ingredient you can see, including ones you do not recognise.
If a field is not present, use "" or []. Never guess.

Korean text:
{text}"""

LABEL_RETRY = """Your previous reply was not valid JSON.

Reply with ONE valid JSON object and nothing else. No prose, no markdown fence.
Keys: product_name, kind, ingredients_ko, ingredients, dosage, dosage_ko.

Korean text:
{text}"""
