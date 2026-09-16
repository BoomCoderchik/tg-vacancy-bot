"""Habr Career public JSON vacancy adapter.

Reads the same public JSON feed that career.habr.com serves its own vacancy
pages (``https://career.habr.com/api/frontend/vacancies``): no API key,
account, or protection bypass is involved. The feed is IT-only and carries the
specialist qualification, skills, divisions, salary, and publication date for
every item. Each item is mapped into a ``Vacancy``; skills become the ``stack``
and the description is composed from the real qualification, division, and
skill fields. Policy, freshness, localization, and SQLite dedup are applied
downstream by the shared publish pipeline; this module never filters by policy
itself.
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

HABR_API_URL = "https://career.habr.com/api/frontend/vacancies"
HABR_PAGE_URL = "https://career.habr.com"
HABR_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0 Safari/537.36",
    "Accept": "application/json",
}
_MAX_STACK_SKILLS = 12


def utcnow() -> datetime:
    return datetime.now(UTC)


class HabrVacancyApiAdapter(SourceAdapter):
    name = "Habr Career"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch(self) -> list[Vacancy]:
        queries = _split_queries(self.settings.habr_api_query)
        wanted = max(self.settings.habr_api_results_wanted, 0)
        if wanted <= 0 or not queries:
            return []
        vacancies: list[Vacancy] = []
        seen_urls: set[str] = set()
        async with source_session(headers=HABR_HEADERS) as session:
            for query in queries:
                if len(vacancies) >= wanted:
                    break
                try:
                    payload = await _fetch_habr_api(session, query, wanted)
                    for vacancy in _items_to_vacancies(payload, seen_urls):
                        vacancies.append(vacancy)
                except Exception as exc:
                    # One failing query must not kill the rest of the cycle.
                    logger.warning("Habr Career fetch failed for %r: %s", query, type(exc).__name__)
        return filter_fresh_vacancies(
            vacancies,
            max_age_hours=self.settings.source_max_age_hours,
            current_time=utcnow(),
            require_published_at=False,
        )


def _split_queries(raw_query: str) -> tuple[str, ...]:
    return tuple(query.strip() for query in raw_query.split("||") if query.strip())


async def _fetch_habr_api(session, query: str, per_page: int) -> Any:
    async with session.get(
        HABR_API_URL,
        params={
            "q": query,
            "sort": "date",
            "per_page": min(max(per_page, 1), 100),
            "page": 1,
        },
    ) as response:
        response.raise_for_status()
        return await response.json()


def _items_to_vacancies(payload: Any, seen_urls: set[str]) -> list[Vacancy]:
    if not isinstance(payload, dict):
        return []
    items = payload.get("list")
    if not isinstance(items, list):
        return []

    vacancies: list[Vacancy] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        href = str(item.get("href") or "").strip()
        if not title or not href:
            continue
        url = f"{HABR_PAGE_URL}{href}" if href.startswith("/") else href
        if url in seen_urls:
            continue
        seen_urls.add(url)
        company = item.get("company") or {}
        locations = [
            str(entry.get("title") or "").strip()
            for entry in (item.get("locations") or [])
            if isinstance(entry, dict) and str(entry.get("title") or "").strip()
        ]
        location: str | None = ", ".join(locations) or None
        if location is None and item.get("remoteWork") is True:
            location = "Remote"
        qualification = str(item.get("qualification") or "").strip() or None
        divisions = [
            str(entry.get("title") or "").strip()
            for entry in (item.get("divisions") or [])
            if isinstance(entry, dict) and str(entry.get("title") or "").strip()
        ]
        skills = [
            str(entry.get("title") or "").strip()
            for entry in (item.get("skills") or [])
            if isinstance(entry, dict) and str(entry.get("title") or "").strip()
        ]
        description = _compose_description(qualification, divisions, skills)
        if not description:
            continue
        salary = _format_salary(item.get("salary")) or _format_salary(item.get("predictedSalary"))
        published = item.get("publishedDate") or {}
        published_at = parse_source_datetime(published.get("date") if isinstance(published, dict) else None)
        raw_text = f"{title}\n{description}"

        vacancies.append(
            Vacancy(
                title=title,
                description=description,
                source=HabrVacancyApiAdapter.name,
                url=url,
                company=str(company.get("title") or "").strip() or None,
                location=location,
                salary=salary,
                stack=tuple(skills[:_MAX_STACK_SKILLS]),
                published_at=published_at,
                raw_text=raw_text,
            )
        )
    return vacancies


def _compose_description(
    qualification: str | None,
    divisions: list[str],
    skills: list[str],
) -> str:
    parts = []
    if qualification:
        parts.append(qualification)
    if divisions:
        parts.append(", ".join(divisions))
    if skills:
        parts.append("Навыки: " + ", ".join(skills))
    return "\n".join(parts)


def _format_salary(salary: Any) -> str | None:
    if not isinstance(salary, dict):
        return None
    formatted = str(salary.get("formatted") or "").strip()
    return formatted or None
