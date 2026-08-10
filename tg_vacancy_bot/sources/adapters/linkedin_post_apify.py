from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import aiohttp

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.sources.base import SourceAdapter, source_session
from tg_vacancy_bot.sources.dates import parse_source_datetime
from tg_vacancy_bot.sources.freshness import filter_fresh_vacancies
from tg_vacancy_bot.sources.adapters.linkedin_post_search import (
    _canonicalize_linkedin_post_url,
    _stack_from_text,
)


APIFY_RUN_SYNC_DATASET_ITEMS_URL = "https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
APIFY_MAX_TIMEOUT_SECONDS = 300
HIRING_INTENT_PATTERN = re.compile(
    r"(?:\bhiring\b|\bwe['’]?re hiring\b|\blooking for\b|\bjoin our team\b|\bopen role\b|"
    r"\bopen position\b|\bvacancy\b|\bwe need\b|\bneed a\b|\bseeking\b|"
    r"\bищем\b|\bнужен(?:а|ы)?\b|\bтребуется\b|\bнанимаем\b|\bв команду\b|\bвакансия\b)",
    re.IGNORECASE,
)
DEVELOPMENT_ROLE_PATTERN = re.compile(
    r"(?:\bfront[-\s]?end\b|\bfrontend\b|\bback[-\s]?end\b|\bbackend\b|"
    r"\bfull[-\s]?stack\b|\bsoftware\s+(?:developer|engineer)\b|"
    r"\b(?:web|mobile|python|java|golang|go|node(?:\.js)?|react|vue|angular|"
    r"typescript|javascript|ai|ml|llm|machine\s+learning)\s+"
    r"(?:developer|engineer|architect|programmer)\b|"
    r"\b(?:developer|engineer|architect|programmer)\s+"
    r"(?:front[-\s]?end|frontend|back[-\s]?end|backend|full[-\s]?stack|software|"
    r"python|java|golang|go|node(?:\.js)?|react|vue|angular|typescript|javascript|ai|ml|llm)\b|"
    r"\b(?:фронтенд|фронт-энд|бэкенд|бекенд|фулстек|фуллстек)\b|"
    r"\b(?:разработчик|инженер|программист)\b)",
    re.IGNORECASE,
)
ROLE_TITLE_PATTERN = re.compile(
    r"\b(?:(?:junior|middle|mid-level|senior|lead|staff|principal)\s+)?"
    r"(?:front[-\s]?end|frontend|back[-\s]?end|backend|full[-\s]?stack|software|web|mobile|"
    r"python|java|golang|go|node(?:\.js)?|react|vue|angular|typescript|javascript|ai|ml|llm)\s+"
    r"(?:developer|engineer|architect|programmer)\b|"
    r"\b(?:фронтенд|фронт-энд|бэкенд|бекенд|фулстек|фуллстек)[-\s]+"
    r"(?:разработчик|инженер|программист)\b",
    re.IGNORECASE,
)


class ApifyProviderError(RuntimeError):
    """Provider failure without echoing the token or response body."""

    def __init__(self, status_code: int | None = None) -> None:
        self.status_code = status_code
        detail = f" (HTTP {status_code})" if status_code is not None else ""
        super().__init__(f"Apify LinkedIn source request failed{detail}")


class LinkedInPostApifyAdapter(SourceAdapter):
    name = "LinkedIn Hiring Posts (Apify)"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch(self) -> list[Vacancy]:
        items = await self._fetch_items()
        vacancies = _items_to_vacancies(items, source=self.name)
        return filter_fresh_vacancies(
            vacancies,
            max_age_hours=self.settings.linkedin_post_max_age_hours,
            current_time=datetime.now(UTC),
            require_published_at=True,
        )

    async def _fetch_items(self) -> list[Mapping[str, Any]]:
        queries = self.settings.linkedin_post_apify_search_queries
        if any(len(query) > 85 for query in queries):
            raise ValueError("LINKEDIN_POST_APIFY_SEARCH_QUERIES entries must be 85 characters or shorter")

        actor_id = self.settings.linkedin_post_apify_actor.strip().replace("/", "~")
        if not actor_id:
            raise ValueError("LINKEDIN_POST_APIFY_ACTOR must not be empty")
        url = APIFY_RUN_SYNC_DATASET_ITEMS_URL.format(actor_id=quote(actor_id, safe="~"))
        payload = {
            "searchQueries": list(queries),
            "postedLimit": self.settings.linkedin_post_apify_posted_limit.strip() or "24h",
            "sortBy": "date",
            "maxPosts": self.settings.linkedin_post_apify_max_posts,
        }
        timeout_seconds = min(
            max(self.settings.linkedin_post_apify_timeout_seconds, 1),
            APIFY_MAX_TIMEOUT_SECONDS,
        )
        params = {
            "timeout": str(timeout_seconds),
            "format": "json",
            "clean": "1",
            "maxItems": str(self.settings.linkedin_post_apify_max_posts * len(queries)),
        }
        request_timeout = aiohttp.ClientTimeout(total=timeout_seconds + 15)
        async with source_session(
            timeout=request_timeout,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.settings.apify_api_token}",
            },
        ) as session:
            async with session.post(url, params=params, json=payload) as response:
                if response.status >= 400:
                    raise ApifyProviderError(response.status)
                try:
                    data = await response.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError) as exc:
                    raise ApifyProviderError(response.status) from exc

        if not isinstance(data, list):
            raise ApifyProviderError()
        return [item for item in data if isinstance(item, Mapping)]


def _items_to_vacancies(items: list[Mapping[str, Any]], *, source: str) -> list[Vacancy]:
    vacancies: list[Vacancy] = []
    seen_urls: set[str] = set()
    for item in items:
        vacancy = _item_to_vacancy(item, source=source)
        if vacancy is None or vacancy.url in seen_urls:
            continue
        seen_urls.add(vacancy.url or "")
        vacancies.append(vacancy)
    return vacancies


def _item_to_vacancy(item: Mapping[str, Any], *, source: str) -> Vacancy | None:
    url = _canonicalize_linkedin_post_url(_first_text(item, "linkedinUrl", "postUrl", "url"))
    content = _first_text(item, "content", "text", "commentary")
    if not url or not content:
        return None
    if not HIRING_INTENT_PATTERN.search(content) or not DEVELOPMENT_ROLE_PATTERN.search(content):
        return None

    published_at = _item_datetime(item)
    if published_at is None:
        return None
    role_match = ROLE_TITLE_PATTERN.search(content) or DEVELOPMENT_ROLE_PATTERN.search(content)
    role = " ".join(role_match.group(0).split()) if role_match else "Software Developer"
    author = item.get("author")
    company = _first_text(author, "name", "universalName") if isinstance(author, Mapping) else ""
    return Vacancy(
        title=role[:120],
        description=" ".join(content.split()),
        source=source,
        url=url,
        company=company or None,
        role=role,
        stack=_stack_from_text(content),
        published_at=published_at,
        raw_text=content,
    )


def _item_datetime(item: Mapping[str, Any]) -> datetime | None:
    posted_at = item.get("postedAt")
    if isinstance(posted_at, Mapping):
        for key in ("date", "timestamp"):
            parsed = parse_source_datetime(posted_at.get(key))
            if parsed is not None:
                return parsed
    for key in ("postedAt", "createdAt", "createdAtISO", "publishedAt", "date"):
        parsed = parse_source_datetime(item.get(key))
        if parsed is not None:
            return parsed
    return None


def _first_text(value: object, *keys: str) -> str:
    if not isinstance(value, Mapping):
        return ""
    for key in keys:
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return ""
