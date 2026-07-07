from datetime import UTC, datetime

from tg_vacancy_bot.sources.dates import parse_source_datetime


def test_parse_source_datetime_accepts_iso_zulu_datetime() -> None:
    parsed = parse_source_datetime("2026-07-05T08:30:00Z")

    assert parsed == datetime(2026, 7, 5, 8, 30, tzinfo=UTC)


def test_parse_source_datetime_accepts_unix_timestamp() -> None:
    parsed = parse_source_datetime(1783209600)

    assert parsed == datetime(2026, 7, 5, tzinfo=UTC)


def test_parse_source_datetime_accepts_rss_pub_date() -> None:
    parsed = parse_source_datetime("Mon, 06 Jul 2026 16:25:02 +0000")

    assert parsed == datetime(2026, 7, 6, 16, 25, 2, tzinfo=UTC)


def test_parse_source_datetime_returns_none_for_blank_or_unknown_values() -> None:
    assert parse_source_datetime("") is None
    assert parse_source_datetime(None) is None
    assert parse_source_datetime("not a date") is None
