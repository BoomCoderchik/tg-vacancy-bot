from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.sources.base import SourceAdapter, source_session
from tg_vacancy_bot.sources.dates import parse_source_datetime


SERPAPI_SEARCH_URL = "https://serpapi.com/search.json"
POST_URL_MARKERS = ("linkedin.com/posts/", "linkedin.com/feed/update/")


class LinkedInPostSearchAdapter(SourceAdapter):
    name = "LinkedIn Hiring Posts"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch(self) -> list[Vacancy]:
        params = {
            "engine": "google",
            "api_key": self.settings.serpapi_api_key,
            "q": self.settings.linkedin_post_search_query,
            "num": self.settings.linkedin_post_search_results_wanted,
            "location": self.settings.linkedin_post_search_location,
            "hl": "ru",
        }
        async with source_session() as session:
            async with session.get(SERPAPI_SEARCH_URL, params=params) as response:
                response.raise_for_status()
                payload = await response.json()

        vacancies = []
        for result in payload.get("organic_results", []):
            if isinstance(result, Mapping):
                vacancy = _result_to_vacancy(result, self.settings.linkedin_post_search_location)
                if vacancy is not None:
                    vacancies.append(vacancy)
        return vacancies


def _result_to_vacancy(result: Mapping[str, Any], location: str) -> Vacancy | None:
    title = _clean_title(_text(result, "title"))
    link = _text(result, "link")
    snippet = _text(result, "snippet")
    if not title or not link or not snippet or not _is_linkedin_post_url(link):
        return None

    return Vacancy(
        title=title,
        description=snippet,
        source=LinkedInPostSearchAdapter.name,
        url=link,
        location=location or None,
        stack=_stack_from_text(f"{title} {snippet}"),
        published_at=_parse_search_date(_text(result, "date")),
        raw_text=f"{title} {snippet}",
    )


def _is_linkedin_post_url(link: str) -> bool:
    lower = link.lower()
    return any(marker in lower for marker in POST_URL_MARKERS)


def _clean_title(title: str) -> str:
    for suffix in (" | LinkedIn", " в LinkedIn", " on LinkedIn"):
        if title.endswith(suffix):
            return title[: -len(suffix)].strip()
    return title


def _stack_from_text(text: str) -> tuple[str, ...]:
    lower = text.lower()
    pairs = (
        ("LinkedIn post", "linkedin"),
        ("frontend", "frontend"),
        ("frontend", "front-end"),
        ("backend", "backend"),
        ("fullstack", "fullstack"),
        ("fullstack", "full-stack"),
        ("designer", "designer"),
        ("AI", "ai engineer"),
        ("ML", "ml engineer"),
        ("LLM", "llm"),
        ("Angular", "angular"),
        ("React", "react"),
        ("TypeScript", "typescript"),
        ("JavaScript", "javascript"),
        ("Python", "python"),
        ("REST API", "rest api"),
    )
    values = ["LinkedIn post"]
    for label, marker in pairs:
        if marker in lower and label not in values:
            values.append(label)
    return tuple(values)


def _text(result: Mapping[str, Any], key: str) -> str:
    value = result.get(key)
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "nat"} else text


def _parse_search_date(value: str) -> datetime | None:
    parsed = parse_source_datetime(value)
    if parsed is not None or not value:
        return parsed
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=UTC)
        except ValueError:
            pass
    return None
