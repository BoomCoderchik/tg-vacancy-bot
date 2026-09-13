from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime


def parse_source_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _to_utc(value)
    if isinstance(value, int | float):
        return _parse_timestamp(value)
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None
    if text.isdigit():
        return _parse_timestamp(int(text))

    normalized = text.removesuffix("Z") + "+00:00" if text.endswith("Z") else text
    try:
        return _to_utc(datetime.fromisoformat(normalized))
    except ValueError:
        pass

    try:
        return _to_utc(parsedate_to_datetime(text))
    except (TypeError, ValueError, IndexError, OverflowError):
        return None


def _parse_timestamp(value: int | float) -> datetime | None:
    timestamp = value / 1000 if value > 10_000_000_000 else value
    try:
        return datetime.fromtimestamp(timestamp, tz=UTC)
    except (OSError, OverflowError, ValueError):
        return None


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


_DAY_OFFSET_WORDS: dict[str, int] = {
    "сегодня": 0,
    "вчера": 1,
    "позавчера": 2,
    "today": 0,
    "yesterday": 1,
}

_RELATIVE_AGO_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(\d+)\s+(?:день|дня|дней)\s+назад"), "days"),
    (re.compile(r"(\d+)\s+(?:час|часа|часов|ч)\s+назад"), "hours"),
    (re.compile(r"(\d+)\s+(?:минуту|минуты|минут)\s+назад"), "minutes"),
    (re.compile(r"(\d+)\s+(?:секунду|секунды|секунд)\s+назад"), "seconds"),
    (re.compile(r"(\d+)\s+(?:неделю|недели|недель)\s+назад"), "weeks"),
    (re.compile(r"(\d+)\s*(?:day|days)\s+ago"), "days"),
    (re.compile(r"(\d+)\s*(?:hour|hours)\s+ago"), "hours"),
    (re.compile(r"(\d+)\s*(?:minute|minutes)\s+ago"), "minutes"),
    (re.compile(r"(\d+)\s*(?:second|seconds)\s+ago"), "seconds"),
    (re.compile(r"(\d+)\s*(?:week|weeks)\s+ago"), "weeks"),
)


def parse_relative_source_datetime(value: str, current_time: datetime) -> datetime | None:
    """Parse a human "N units ago" timestamp relative to ``current_time``.

    Case-insensitive with flexible whitespace. Supports Russian and English
    day/hour/minute/week (plus seconds) phrases and bare today/yesterday
    words. Returns an aware UTC datetime or ``None`` when unrecognized.
    """

    if not isinstance(value, str):
        return None
    text = " ".join(value.lower().replace(".", "").split())
    if not text:
        return None
    base = _to_utc(current_time)
    if text in _DAY_OFFSET_WORDS:
        return base - timedelta(days=_DAY_OFFSET_WORDS[text])
    for pattern, unit in _RELATIVE_AGO_PATTERNS:
        match = pattern.match(text)
        if not match:
            continue
        try:
            amount = int(match.group(1))
        except ValueError:
            return None
        if amount < 0:
            return None
        return base - timedelta(**{unit: amount})
    return None
