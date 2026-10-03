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


def test_takes_the_first_full_date_when_several_are_present():
    assert parse_korean_date("발행 2026년 9월 1일 / 기한 2026년 10월 5일") == date(2026, 9, 1)
