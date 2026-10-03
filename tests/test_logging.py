import logging

from ilgeojwo.events import ScanEvent, log_scan


def test_a_scan_is_logged_with_timings_and_outcome(caplog):
    with caplog.at_level(logging.INFO, logger="ilgeojwo"):
        log_scan(ScanEvent(lens="label", status="ok", ocr_ms=3400, llm_ms=9100,
                           ocr_chars=118, warnings=3, approximate=2))
    line = caplog.text
    assert "lens=label" in line
    assert "status=ok" in line
    assert "ocr=3400ms" in line
    assert "llm=9100ms" in line
    assert "warnings=3" in line
    assert "approximate=2" in line


def test_the_log_never_contains_what_was_scanned(caplog):
    """The whole claim is that her documents stay on her machine. A log file is
    still on her machine, but it is the one place content leaks by habit — into
    a pastebin, a screenshot, a bug report."""
    secret = "출입국관리사무소 여권번호 M12345678 서울시 관악구"
    with caplog.at_level(logging.INFO, logger="ilgeojwo"):
        log_scan(ScanEvent(lens="document", status="ok", ocr_ms=1, llm_ms=1,
                           ocr_chars=len(secret), warnings=0, approximate=0))
    assert "M12345678" not in caplog.text
    assert "출입국" not in caplog.text
    assert "관악구" not in caplog.text
    assert f"chars={len(secret)}" in caplog.text


def test_a_failure_is_logged_with_its_kind_but_not_its_payload(caplog):
    with caplog.at_level(logging.WARNING, logger="ilgeojwo"):
        log_scan(ScanEvent(lens="label", status="unreadable", ocr_ms=2200,
                           llm_ms=0, ocr_chars=3, warnings=0, approximate=0))
    assert "status=unreadable" in caplog.text
    assert caplog.records[-1].levelno == logging.WARNING


def test_an_ok_scan_is_info_not_warning(caplog):
    with caplog.at_level(logging.INFO, logger="ilgeojwo"):
        log_scan(ScanEvent(lens="document", status="ok", ocr_ms=1, llm_ms=1,
                           ocr_chars=10, warnings=0, approximate=0))
    assert caplog.records[-1].levelno == logging.INFO
