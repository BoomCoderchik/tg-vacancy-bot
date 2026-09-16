"""HeadHunter public API vacancy adapter.

Reads the official HeadHunter JSON vacancy search (``https://api.hh.ru/vacancies``),
which allows anonymous search but requires a ``User-Agent`` header with a real
contact email. The adapter registers only when ``HH_API_CONTACT_EMAIL`` is set;
without it the provider answers ``400 Bad User-Agent`` and the query is skipped
with a warning instead of being retried with a forged header. Each item is
mapped into a ``Vacancy`` with company, region, salary, and publication date.
Policy, freshness, localization, and SQLite dedup are applied downstream by the
shared publish pipeline; this module never filters by policy itself.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.sources.base import SourceAdapter, html_to_text, source_session
from tg_vacancy_bot.sources.dates import parse_source_datetime
from tg_vacancy_bot.sources.freshness import filter_fresh_vacancies

logger = logging.getLogger(__name__)

HH_API_URL = "https://api.hh.ru/vacancies"

_CURRENCY_SYMBOLS = {
    "RUR": "\u20bd",
    "RUB": "\u20bd",
    "KZT": "\u20b8",
    "USD": "$",
    "EUR": "\u20ac",
    "AZN": "\u20bc",
    "UZS": "сум",
    "KGS": "сом",
    "BYN": "Br",
}


def utcnow() -> datetime:
    return datetime.now(UTC)


class HeadHunterApiAdapter(SourceAdapter):
    name = "HeadHunter API"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch(self) -> list[Vacancy]:
        contact = self.settings.hh_api_contact_email.strip()
        queries = _split_queries(self.settings.hh_api_query)
        wanted = max(self.settings.hh_api_results_wanted, 0)
        if wanted <= 0 or not queries or not contact:
            if self.settings.enable_hh_api and not contact:
                logger.warning("HeadHunter API skipped: HH_API_CONTACT_EMAIL is empty.")
            return []
        headers = {
            "User-Agent": f"TGVacancyBot/1.0 ({contact})",
            "Accept": "application/json",
        }
        vacancies: list[Vacancy] = []
        seen_urls: set[str] = set()
        async with source_session(headers=headers) as session:
            for query in queries:
                if len(vacancies) >= wanted:
                    break
                try:
                    payload = await _fetch_hh_api(session, query, wanted)
                    for vacancy in _items_to_vacancies(payload, seen_urls):
                        vacancies.append(vacancy)
                except Exception as exc:
                    # One failing query must not kill the rest of the cycle.
                    logger.warning("HeadHunter API fetch failed for %r: %s", query, type(exc).__name__)
        return filter_fresh_vacancies(
            vacancies,
            max_age_hours=self.settings.source_max_age_hours,
            current_time=utcnow(),
            require_published_at=False,
        )


def _split_queries(raw_query: str) -> tuple[str, ...]:
    return tuple(query.strip() for query in raw_query.split("||") if query.strip())


async def _fetch_hh_api(session, query: str, per_page: int) -> Any:
    async with session.get(
        HH_API_URL,
        params={
            "text": query,
            "per_page": min(max(per_page, 1), 100),
            "page": 0,
            "order_by": "publication_time",
        },
    ) as response:
        response.raise_for_status()
        return await response.json()


def _items_to_vacancies(payload: Any, seen_urls: set[str]) -> list[Vacancy]:
    if not isinstance(payload, dict):
        return []
    items = payload.get("items")
    if not isinstance(items, list):
        return []

    vacancies: list[Vacancy] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        url = str(item.get("alternate_url") or "").strip()
        title = str(item.get("name") or "").strip()
        if not url or not title or url in seen_urls:
            continue
        seen_urls.add(url)
        employer = item.get("employer") or {}
        area = item.get("area") or {}
        snippet = item.get("snippet") or {}
        description = _snippet_text(snippet)
        if not description:
            continue
        salary = _format_salary(item.get("salary"))
        published_at = parse_source_datetime(item.get("published_at"))
        raw_text = f"{title}\n{description}"

        vacancies.append(
            Vacancy(
                title=title,
                description=description,
                source=HeadHunterApiAdapter.name,
                url=url,
                company=str(employer.get("name") or "").strip() or None,
                location=str(area.get("name") or "").strip() or None,
                salary=salary,
                stack=(),
                published_at=published_at,
                raw_text=raw_text,
            )
        )
    return vacancies


def _snippet_text(snippet: Any) -> str:
    if not isinstance(snippet, dict):
        return ""
    parts = [
        html_to_text(str(snippet.get("requirement") or "")),
        html_to_text(str(snippet.get("responsibility") or "")),
    ]
    return "\n\n".join(part.strip() for part in parts if part.strip())


def _format_salary(salary: Any) -> str | None:
    if not isinstance(salary, dict):
        return None
    currency = _CURRENCY_SYMBOLS.get(str(salary.get("currency") or "").upper())
    if currency is None:
        currency = str(salary.get("currency") or "").strip() or None
    parts = []
    if salary.get("from") is not None:
        parts.append(f"от {salary.get('from')}")
    if salary.get("to") is not None:
        parts.append(f"до {salary.get('to')}")
    if not parts:
        return None
    text = " ".join(parts)
    if currency:
        text = f"{text} {currency}"
    return text
