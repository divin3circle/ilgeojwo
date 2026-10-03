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
