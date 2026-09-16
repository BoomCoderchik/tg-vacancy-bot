"""Работа России open-data vacancy adapter.

Reads the official government open-data JSON API
(``https://opendata.trudvsem.ru/api/v1/vacancies``): plain GET requests, no
key, account, or protection bypass is involved. Each vacancy already carries
its duties, requirements, skills, salary bounds, and modification date, which
are mapped into a ``Vacancy``. Contact details from the payload (phones,
emails, contact persons) are never mapped into published cards. Policy,
freshness, localization, and SQLite dedup are applied downstream by the shared
publish pipeline; this module never filters by policy itself.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.sources.base import SourceAdapter, source_session
from tg_vacancy_bot.sources.dates import parse_source_datetime
from tg_vacancy_bot.sources.freshness import filter_fresh_vacancies

logger = logging.getLogger(__name__)

TRUDVSEM_API_URL = "https://opendata.trudvsem.ru/api/v1/vacancies"
TRUDVSEM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0 Safari/537.36",
    "Accept": "application/json",
}


def utcnow() -> datetime:
    return datetime.now(UTC)


class TrudvsemApiAdapter(SourceAdapter):
    name = "Работа России"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch(self) -> list[Vacancy]:
        queries = _split_queries(self.settings.trudvsem_api_query)
        wanted = max(self.settings.trudvsem_api_results_wanted, 0)
        if wanted <= 0 or not queries:
            return []
        vacancies: list[Vacancy] = []
        seen_urls: set[str] = set()
        async with source_session(headers=TRUDVSEM_HEADERS) as session:
            for query in queries:
                if len(vacancies) >= wanted:
                    break
                try:
                    payload = await _fetch_trudvsem_api(session, query, wanted)
                    for vacancy in _items_to_vacancies(payload, seen_urls):
                        vacancies.append(vacancy)
                except Exception as exc:
                    # One failing query must not kill the rest of the cycle.
                    logger.warning("Trudvsem fetch failed for %r: %s", query, type(exc).__name__)
        return filter_fresh_vacancies(
            vacancies,
            max_age_hours=self.settings.source_max_age_hours,
            current_time=utcnow(),
            require_published_at=False,
        )


def _split_queries(raw_query: str) -> tuple[str, ...]:
    return tuple(query.strip() for query in raw_query.split("||") if query.strip())


async def _fetch_trudvsem_api(session, query: str, per_page: int) -> Any:
    async with session.get(
        TRUDVSEM_API_URL,
        params={
            "text": query,
            "limit": min(max(per_page, 1), 100),
            "offset": 0,
        },
    ) as response:
        response.raise_for_status()
        return await response.json()


def _items_to_vacancies(payload: Any, seen_urls: set[str]) -> list[Vacancy]:
    if not isinstance(payload, dict):
        return []
    results = payload.get("results")
    entries = results.get("vacancies") if isinstance(results, dict) else None
    if not isinstance(entries, list):
        return []

    vacancies: list[Vacancy] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        item = entry.get("vacancy")
        if not isinstance(item, dict):
            continue
        title = str(item.get("job-name") or "").strip()
        url = str(item.get("vac_url") or "").strip()
        if not title or not url or url in seen_urls:
            continue
        seen_urls.add(url)
        company = item.get("company") or {}
        region = item.get("region") or {}
        description = _compose_description(item)
        if not description:
            continue
        salary = str(item.get("salary") or "").strip() or None
        published_at = parse_source_datetime(item.get("date_modify"))
        if published_at is None:
            published_at = parse_source_datetime(item.get("creation-date"))
        raw_text = f"{title}\n{description}"

        vacancies.append(
            Vacancy(
                title=title,
                description=description,
                source=TrudvsemApiAdapter.name,
                url=url,
                company=str(company.get("name") or "").strip() or None,
                location=str(region.get("name") or "").strip() or None,
                salary=salary,
                stack=tuple(_skills(item)),
                published_at=published_at,
                raw_text=raw_text,
            )
        )
    return vacancies


def _compose_description(item: dict) -> str:
    parts = [
        str(item.get("duty") or "").strip(),
        str(item.get("requirements") or "").strip(),
        str(item.get("requirement") or "").strip()
        if isinstance(item.get("requirement"), str)
        else "",
    ]
    skills = _skills(item)
    if skills:
        parts.append("Навыки: " + ", ".join(skills))
    return "\n\n".join(part for part in parts if part)


def _skills(item: dict) -> list[str]:
    skills = item.get("skills")
    if not isinstance(skills, list):
        return []
    return [str(skill).strip() for skill in skills if str(skill).strip()]
