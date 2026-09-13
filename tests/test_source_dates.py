from datetime import UTC, datetime, timedelta

import pytest

from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.sources.dates import parse_relative_source_datetime, parse_source_datetime
from tg_vacancy_bot.sources.freshness import filter_fresh_vacancies


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


def test_filter_fresh_vacancies_can_require_a_recent_publication_date() -> None:
    now = datetime(2026, 7, 10, tzinfo=UTC)
    vacancies = [
        Vacancy(title="Recent", description="", source="LinkedIn", published_at=now - timedelta(hours=120)),
        Vacancy(title="Old", description="", source="LinkedIn", published_at=now - timedelta(hours=120, seconds=1)),
        Vacancy(title="Undated", description="", source="LinkedIn"),
    ]

    assert [vacancy.title for vacancy in filter_fresh_vacancies(
        vacancies,
        max_age_hours=120,
        current_time=now,
        require_published_at=True,
    )] == ["Recent"]


@pytest.mark.parametrize(
    ("value", "expected_delta"),
    [
        ("сегодня", timedelta(days=0)),
        ("вчера", timedelta(days=1)),
        ("позавчера", timedelta(days=2)),
        ("1 день назад", timedelta(days=1)),
        ("2 дня назад", timedelta(days=2)),
        ("5 дней назад", timedelta(days=5)),
        ("5 часов назад", timedelta(hours=5)),
        ("2 часа назад", timedelta(hours=2)),
        ("45 минут назад", timedelta(minutes=45)),
        ("1 минуту назад", timedelta(minutes=1)),
        ("3 минуты назад", timedelta(minutes=3)),
        ("30 секунд назад", timedelta(seconds=30)),
        ("1 неделю назад", timedelta(weeks=1)),
        ("2 недели назад", timedelta(weeks=2)),
        ("5 недель назад", timedelta(weeks=5)),
        ("today", timedelta(days=0)),
        ("yesterday", timedelta(days=1)),
        ("1 day ago", timedelta(days=1)),
        ("2 days ago", timedelta(days=2)),
        ("5 hours ago", timedelta(hours=5)),
        ("45 minutes ago", timedelta(minutes=45)),
        ("10 seconds ago", timedelta(seconds=10)),
        ("1 week ago", timedelta(weeks=1)),
        ("2 weeks ago", timedelta(weeks=2)),
    ],
)
def test_parse_relative_source_datetime(value: str, expected_delta: timedelta) -> None:
    current_time = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)

    assert parse_relative_source_datetime(value, current_time) == current_time - expected_delta


@pytest.mark.parametrize(
    ("value", "expected_delta"),
    [
        ("  СЕГОДНЯ ", timedelta(days=0)),
        ("  ВчеРА  ", timedelta(days=1)),
        ("ПозАвчерА", timedelta(days=2)),
        ("  2   ДНЯ   НАЗАД  ", timedelta(days=2)),
        ("5 ч. назад", timedelta(hours=5)),
        ("  TODAY ", timedelta(days=0)),
        ("2 DaYs AgO", timedelta(days=2)),
    ],
)
def test_parse_relative_source_datetime_is_case_and_whitespace_flexible(
    value: str, expected_delta: timedelta
) -> None:
    current_time = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)

    assert parse_relative_source_datetime(value, current_time) == current_time - expected_delta


def test_parse_relative_source_datetime_converts_naive_current_time_to_utc() -> None:
    parsed = parse_relative_source_datetime("2 часа назад", datetime(2026, 7, 19, 12, 0))

    assert parsed == datetime(2026, 7, 19, 10, 0, tzinfo=UTC)


@pytest.mark.parametrize("value", ["", "не распознано", "next month", "завтра", "tomorrow", "5 лет назад"])
def test_parse_relative_source_datetime_returns_none_for_unrecognized(value: str) -> None:
    current_time = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)

    assert parse_relative_source_datetime(value, current_time) is None
