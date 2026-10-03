"""Prompts. The model transcribes and extracts; it never judges (spec §5.1)."""

DOCUMENT = """You are reading text that was scanned from a Korean document.
Extract only what is literally present. Do not add, infer, or assume anything.

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

DOCUMENT_RETRY = """Your previous reply was not valid JSON.

Reply with ONE valid JSON object and nothing else. No prose, no markdown fence.
Keys: doc_type, sender, action, deadline_text, issued_text, amount, location.
Use "" for anything not present in the text.

Korean text:
{text}"""
