from __future__ import annotations

from dataclasses import dataclass

import feedparser

from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.parser import extract_stack

from .base import SourceAdapter, html_to_text, source_session
from .dates import parse_source_datetime


@dataclass(frozen=True)
class RssFeedConfig:
    source_name: str
    url: str
    default_location: str = "Remote"
    limit: int = 80


class RssFeedAdapter(SourceAdapter):
    def __init__(self, config: RssFeedConfig) -> None:
        self.name = config.source_name
        self.url = config.url
        self.default_location = config.default_location
        self.limit = config.limit

    async def fetch(self) -> list[Vacancy]:
        async with source_session() as session:
            async with session.get(self.url) as response:
                response.raise_for_status()
                xml_text = await response.text()

        feed = feedparser.parse(xml_text)
        result: list[Vacancy] = []
        for item in feed.entries[: self.limit]:
            title = item.get("title") or "IT Vacancy"
            description = html_to_text(_entry_description(item))
            link = item.get("link") or item.get("id")
            result.append(
                Vacancy(
                    title=title,
                    company=_company_from_title(title),
                    location=self.default_location,
                    description=description,
                    source=self.name,
                    url=link,
                    stack=extract_stack(" ".join([title, description])),
                    published_at=parse_source_datetime(item.get("published") or item.get("updated")),
                    raw_text=description,
                )
            )
        return result


def _entry_description(item: dict) -> str:
    content = item.get("content") or []
    if content and isinstance(content, list):
        first = content[0]
        if isinstance(first, dict) and first.get("value"):
            return str(first["value"])
    return str(item.get("summary") or item.get("description") or "")


def _company_from_title(title: str) -> str | None:
    for separator in (" at ", " @ ", " - "):
        if separator in title:
            candidate = title.rsplit(separator, 1)[-1].strip()
            if 1 < len(candidate) <= 120:
                return candidate
    return None
