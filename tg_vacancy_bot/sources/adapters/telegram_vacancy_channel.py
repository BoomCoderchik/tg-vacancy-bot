from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

from bs4 import BeautifulSoup, Tag

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.sources.base import SourceAdapter, html_to_text, source_session
from tg_vacancy_bot.sources.dates import parse_relative_source_datetime, parse_source_datetime
from tg_vacancy_bot.sources.freshness import filter_fresh_vacancies
from tg_vacancy_bot.sources.search_providers import BROWSER_HEADERS


logger = logging.getLogger(__name__)

_MONTH_BY_NAME = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_TIME_ONLY_PATTERN = re.compile(r"^\d{1,2}:\d{2}$")


def utcnow() -> datetime:
    return datetime.now(UTC)


class TelegramVacancyChannelAdapter(SourceAdapter):
    name = "Telegram Vacancy Channels"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch(self) -> list[Vacancy]:
        channels = self.settings.russia_telegram_channels
        if not channels:
            return []
        limit = self.settings.russia_telegram_max_posts_per_channel
        vacancies: list[Vacancy] = []
        seen_urls: set[str] = set()
        async with source_session(headers=BROWSER_HEADERS) as session:
            for username in channels:
                try:
                    channel_vacancies = await _fetch_channel(session, username, limit, seen_urls)
                    vacancies.extend(channel_vacancies)
                except Exception as exc:
                    # One private, blocked, or failing channel must not kill the
                    # rest of the cycle; the remaining channels still run.
                    logger.warning(
                        "Failed to fetch Telegram channel %s: %s",
                        username,
                        type(exc).__name__,
                    )
        return filter_fresh_vacancies(
            vacancies,
            max_age_hours=self.settings.source_max_age_hours,
            current_time=utcnow(),
            require_published_at=False,
        )


async def _fetch_channel(session, username: str, limit: int, seen_urls: set[str]) -> list[Vacancy]:
    url = f"https://t.me/s/{username}"
    async with session.get(url) as response:
        if response.status == 404:
            logger.warning("Telegram channel %s not found (HTTP 404)", username)
            return []
        if "/login" in str(response.url):
            logger.warning("Telegram channel %s redirected to the login page", username)
            return []
        response.raise_for_status()
        html = await response.text()

    soup = BeautifulSoup(html, "html.parser")
    vacancies: list[Vacancy] = []
    for block in soup.select("div.tgme_widget_message"):
        if len(vacancies) >= limit:
            break
        vacancy = _post_to_vacancy(block, username, seen_urls)
        if vacancy is not None:
            vacancies.append(vacancy)
    return vacancies


def _post_to_vacancy(block: Tag, username: str, seen_urls: set[str]) -> Vacancy | None:
    post_id, post_url = _extract_post_url(block, username)
    if post_url is None or post_id is None:
        # A valid message must carry its post identifier and link.
        return None
    if post_url in seen_urls:
        return None

    text_element = block.select_one(".tgme_widget_message_text")
    if text_element is None:
        return None
    description = html_to_text(str(text_element))
    if not description:
        # Do not publish posts without a real text.
        return None

    title = _post_title(description)
    date_element = block.select_one("a.tgme_widget_message_date")
    published_at = _published_at_for_post(date_element, utcnow())

    seen_urls.add(post_url)
    return Vacancy(
        title=title,
        description=description,
        source=f"Telegram ({username})",
        url=post_url,
        published_at=published_at,
        location=None,
        stack=(),
        salary=None,
        raw_text=f"{title}\n{description}",
    )


def _extract_post_url(block: Tag, username: str) -> tuple[str | None, str | None]:
    data_post = block.get("data-post")
    if data_post and isinstance(data_post, str) and "/" in data_post:
        post_id = data_post.split("/", 1)[1]
        if post_id:
            return post_id, f"https://t.me/{username}/{post_id}"

    date_link = block.select_one("a.tgme_widget_message_date")
    if date_link is None:
        return None, None
    href = date_link.get("href")
    if not href or not isinstance(href, str):
        return None, None
    post_id = href.rstrip("/").rsplit("/", 1)[-1]
    if not post_id:
        return None, None
    return post_id, href


def _post_title(text: str) -> str:
    normalized = " ".join((text or "").strip().split())
    if not normalized:
        return ""
    if len(normalized) <= 120:
        return normalized
    head = normalized[:120]
    if " " in head:
        return head.rsplit(" ", 1)[0]
    return head


def _published_at_for_post(date_element: Tag | None, current_time: datetime) -> datetime | None:
    if date_element is None:
        return None

    time_tag = date_element.find("time")
    if time_tag is not None:
        attribute = time_tag.get("datetime")
        if attribute:
            parsed = parse_source_datetime(str(attribute))
            if parsed is not None:
                return parsed
        text = time_tag.get_text(strip=True)
        if text:
            return _parse_fallback_date_text(text, current_time)

    text = date_element.get_text(strip=True)
    if text:
        return _parse_fallback_date_text(text, current_time)
    return None


def _parse_fallback_date_text(text: str, current_time: datetime) -> datetime | None:
    text = (text or "").strip()
    if not text:
        return None

    if _TIME_ONLY_PATTERN.match(text):
        hours, minutes = (int(part) for part in text.split(":"))
        base = _as_utc(current_time)
        return base.replace(hour=hours, minute=minutes, second=0, microsecond=0)

    relative = parse_relative_source_datetime(text, current_time)
    if relative is not None:
        return relative

    return _parse_month_day(text, current_time)


def _parse_month_day(text: str, current_time: datetime) -> datetime | None:
    parts = text.replace(",", "").split()
    if len(parts) != 2:
        return None

    month = None
    day = None
    if parts[1].isdigit() and parts[0].lower()[:3] in _MONTH_BY_NAME:
        month = _MONTH_BY_NAME[parts[0].lower()[:3]]
        day = parts[1]
    elif parts[0].isdigit() and parts[1].lower()[:3] in _MONTH_BY_NAME:
        month = _MONTH_BY_NAME[parts[1].lower()[:3]]
        day = parts[0]
    if month is None or day is None:
        return None

    try:
        day_number = int(day)
    except ValueError:
        return None
    if day_number < 1 or day_number > 31:
        return None

    now = _as_utc(current_time)
    try:
        candidate = datetime(now.year, month, day_number, tzinfo=UTC)
    except ValueError:
        return None
    if candidate > now:
        candidate = datetime(now.year - 1, month, day_number, tzinfo=UTC)
    return candidate


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)