"""SQLite persistence. Lens-specific fields live inside card_json (spec §6)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL,
    lens        TEXT NOT NULL,
    image_path  TEXT NOT NULL,
    ocr_text    TEXT NOT NULL,
    card_json   TEXT NOT NULL,
    status      TEXT NOT NULL
);
"""


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path: Path) -> None:
    with _connect(path) as conn:
        conn.executescript(_SCHEMA)


def save_scan(path: Path, *, lens: str, image_path: str, ocr_text: str,
              card_json: str, status: str) -> int:
    init_db(path)
    with _connect(path) as conn:
        cur = conn.execute(
            "INSERT INTO scans (created_at, lens, image_path, ocr_text, card_json, status)"
            " VALUES (?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), lens, image_path,
             ocr_text, card_json, status),
        )
        return int(cur.lastrowid)


def _deadline_key(row: sqlite3.Row) -> tuple[int, str]:
    """Undated cards sort last (spec §3.1) without inventing a date for them."""
    try:
        deadline = json.loads(row["card_json"]).get("deadline")
    except json.JSONDecodeError:
        deadline = None
    return (1, "") if not deadline else (0, str(deadline))


def list_scans(path: Path) -> list[dict]:
    init_db(path)
    with _connect(path) as conn:
        rows = conn.execute("SELECT * FROM scans").fetchall()
    return [dict(r) for r in sorted(rows, key=_deadline_key)]


def get_scan(path: Path, scan_id: int) -> dict | None:
    init_db(path)
    with _connect(path) as conn:
        row = conn.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
    return dict(row) if row else None
