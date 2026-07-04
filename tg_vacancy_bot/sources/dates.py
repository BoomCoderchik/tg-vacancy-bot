from __future__ import annotations

from datetime import UTC, datetime


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
