from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.parser import extract_stack, guess_title

from ..base import SourceAdapter, source_session
from ..dates import parse_source_datetime


HIRING_ROLE_RE = re.compile(
    r"(?:we\s+are\s+)?(?:hiring|looking\s+for|seeking|ищем|ищет)\s+(?:an?\s+)?"
    r"(?P<title>(?:(?:junior|middle|senior|lead|staff|principal)\s+)?"
    r"(?:[\w+#./-]+\s+){0,4}(?:developer|engineer|designer|architect))",
    re.IGNORECASE,
)


class XCrawlXPostsAdapter(SourceAdapter):
    """Reads public X account timelines through the configured XCrawl API."""

    name = "XCrawl X Posts"
    url = "https://run.xcrawl.com/v1/data"

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.xcrawl_api_key
        self._handles = settings.xcrawl_x_handles
        self._max_tweets = settings.xcrawl_x_max_tweets
        self._pages = settings.xcrawl_x_pages

    async def fetch(self) -> list[Vacancy]:
        vacancies: list[Vacancy] = []
        async with source_session(headers={"Authorization": f"Bearer {self._api_key}"}) as session:
            for handle in self._handles:
                async with session.post(
                    self.url,
                    json={
                        "engine": "x_user_tweets",
                        "screen_name": handle,
                        "max_tweets": self._max_tweets,
                        "pages": self._pages,
                        "delay": 1,
                    },
                ) as response:
                    response.raise_for_status()
                    payload = await response.json()
                vacancies.extend(_payload_to_vacancies(payload, handle))
        return vacancies


def _payload_to_vacancies(payload: object, handle: str) -> list[Vacancy]:
    if not isinstance(payload, Mapping):
        raise RuntimeError("XCrawl X User Tweets API returned an invalid response.")

    user = payload.get("user")
    company = _text(user, "name") if isinstance(user, Mapping) else None
    result: list[Vacancy] = []
    for tweet in payload.get("tweets", []):
        if not isinstance(tweet, Mapping):
            continue
        tweet_id = _text(tweet, "id")
        text = _text(tweet, "full_text") or _text(tweet, "text")
        if not tweet_id or not text:
            continue
        result.append(
            Vacancy(
                title=_vacancy_title(text),
                company=company,
                description=text,
                source=XCrawlXPostsAdapter.name,
                url=f"https://x.com/{handle}/status/{tweet_id}",
                stack=extract_stack(text),
                published_at=parse_source_datetime(tweet.get("created_at")),
                raw_text=text,
            )
        )
    return result


def _text(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    return str(item).strip() if item is not None else ""


def _vacancy_title(text: str) -> str:
    match = HIRING_ROLE_RE.search(text)
    if match:
        return " ".join(match.group("title").split())
    return guess_title(text)
