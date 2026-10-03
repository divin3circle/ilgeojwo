import json

from ilgeojwo.store.db import get_scan, init_db, list_scans, save_scan


def _save(db, deadline, lens="document", ocr="출입국관리사무소 체류기간 연장"):
    return save_scan(db, lens=lens, image_path="/tmp/a.jpg", ocr_text=ocr,
                     card_json=json.dumps({"deadline": deadline}), status="ok")


def test_a_saved_scan_can_be_read_back(tmp_path):
    db = tmp_path / "t.db"
    init_db(db)
    sid = _save(db, "2026-10-05")
    row = get_scan(db, sid)
    assert row["lens"] == "document"
    assert row["status"] == "ok"
    assert json.loads(row["card_json"])["deadline"] == "2026-10-05"


def test_soonest_deadline_first_with_undated_cards_last(tmp_path):
    db = tmp_path / "t.db"
    init_db(db)
    _save(db, None)
    _save(db, "2026-12-01")
    _save(db, "2026-10-05")
    assert [json.loads(r["card_json"])["deadline"] for r in list_scans(db)] == [
        "2026-10-05", "2026-12-01", None]


def test_the_same_document_uploaded_twice_gives_two_distinguishable_rows(tmp_path):
    """Review Focus 5: no crash, no silent overwrite, no merged deadline."""
    db = tmp_path / "t.db"
    init_db(db)
    a, b = _save(db, "2026-10-05"), _save(db, "2026-10-05")
    assert a != b
    rows = list_scans(db)
    assert len(rows) == 2
    assert {r["id"] for r in rows} == {a, b}


def test_init_db_is_idempotent(tmp_path):
    db = tmp_path / "t.db"
    init_db(db)
    init_db(db)
    assert list_scans(db) == []


def test_unknown_id_returns_none_rather_than_raising(tmp_path):
    db = tmp_path / "t.db"
    init_db(db)
    assert get_scan(db, 999) is None
