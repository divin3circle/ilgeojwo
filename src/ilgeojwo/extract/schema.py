"""Card shapes. Absence strings live here, verbatim from spec §3."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

ABSENT = {
    "doc_type": "Unidentified document",
    "sender": "Unknown sender",
    "action": "No clear action found",
    "deadline": "No date found",
    "amount": "No amount found",
}


class DocumentCard(BaseModel):
    doc_type: str = ABSENT["doc_type"]
    sender: str = ABSENT["sender"]
    action: str = ABSENT["action"]
    deadline: date | None = None
    deadline_text: str = ""
    amount: str = ABSENT["amount"]
    location: str = ""
    # True when the model would not translate the English-facing fields. She
    # cannot read Korean, so leaving Korean there silently is a failed read.
    untranslated: bool = False


LABEL_ABSENT = {
    "product_name": "Unidentified product",
    "kind": "Unknown",
    "dosage": "Dosage not found — ask the pharmacist",
    "no_ingredients": ("Could not identify the ingredients in this photo. "
                       "Do not rely on this. Show the box to the pharmacist."),
}


class LabelCard(BaseModel):
    product_name: str = LABEL_ABSENT["product_name"]
    kind: str = LABEL_ABSENT["kind"]
    # Korean as printed, kept only when it is actually in the scanned text.
    # The model measurably renamed pseudoephedrine to "cetirizine", so its
    # output is not evidence about the box (spec §5.1 applies to reading too).
    ingredients_ko: list[str] = []
    # What the model claimed but the scan does not support. Shown as doubtful,
    # never as an ingredient, and still screened for risk.
    ingredients_unverified: list[str] = []
    ingredients: list[str] = []
    dosage: str = LABEL_ABSENT["dosage"]
    # Verbatim Korean. The model measurably mistranslated a frequency
    # ("1일 3회" -> "once daily"), so the printed text is what she can check.
    dosage_ko: str = ""
    warnings: list[dict] = []
    ingredients_found: bool = False
