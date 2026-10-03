from datetime import date

import pytest

from ilgeojwo.extract.dates import parse_korean_date


@pytest.mark.parametrize("raw,expected", [
    ("2026년 10월 5일", date(2026, 10, 5)),
    ("2026년10월5일", date(2026, 10, 5)),
    ("2026. 10. 5.", date(2026, 10, 5)),
    ("2026.10.05", date(2026, 10, 5)),
    ("2026-10-05", date(2026, 10, 5)),
    ("2026/10/05", date(2026, 10, 5)),
    ("납부기한: 2026년 10월 5일까지", date(2026, 10, 5)),
])
def test_parses_the_korean_date_formats_she_will_actually_meet(raw, expected):
    assert parse_korean_date(raw) == expected


@pytest.mark.parametrize("raw", [
    "",
    "없음",
    "곧",
    "2026년",
    "10월",
    "2026년 13월 5일",   # impossible month
    "2026년 2월 30일",   # impossible day
])
def test_returns_none_rather_than_a_date_it_cannot_justify(raw):
    assert parse_korean_date(raw) is None


def test_a_date_with_no_year_is_none_not_this_year():
    """Review Focus 5 / spec §3.1: assuming the year is an inference, and the
    spec forbids inferring deadlines. She still sees the Korean verbatim."""
    assert parse_korean_date("10월 5일까지") is None
    assert parse_korean_date("기한 10. 5.") is None





@pytest.mark.parametrize("raw,expected", [
    ("2026.10.1~2026.10.5", date(2026, 10, 5)),
    ("신청기간: 2026년 10월 1일 ~ 2026년 10월 5일", date(2026, 10, 5)),
    ("접수기간 2026-10-01 ~ 2026-10-05", date(2026, 10, 5)),
    ("발행 2026년 9월 1일 / 기한 2026년 10월 5일", date(2026, 10, 5)),
])
def test_the_later_date_wins_because_a_korean_range_puts_the_deadline_last(raw, expected):
    """Korean forms a deadline as 접수기간 A~B or 신청기간 A ~ B, and the
    actionable date is B. An earlier version took the first match, which on
    '발행 … / 기한 …' returned the ISSUE date — the substitution Review Focus 1
    exists to forbid."""
    assert parse_korean_date(raw) == expected


@pytest.mark.parametrize("raw", [
    "제2026-10-05호",
    "문서번호 출입국-2026-09-30",
    "제 2026-10-05 호",
])
def test_a_document_reference_number_is_not_a_deadline(raw):
    assert parse_korean_date(raw) is None


@pytest.mark.parametrize("raw", ["단기 4359년 10월 5일", "7026년 10월 5일", "1026-10-05"])
def test_an_implausible_year_is_rejected_rather_than_displayed_as_a_deadline(raw):
    """A 2026->7026 misread would otherwise display and sort as a real deadline."""
    assert parse_korean_date(raw) is None
