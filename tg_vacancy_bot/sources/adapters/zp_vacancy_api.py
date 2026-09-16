"""Zarplata.ru public API vacancy adapter.

Reads the official Zarplata.ru JSON vacancy search
(``https://api.zarplata.ru/vacancies``) with plain anonymous GET requests: no
key, account, or protection bypass is involved. The provider captcha-limits
anonymous calls, so error and captcha answers are skipped with a warning
instead of being bypassed or retried aggressively. Each item mirrors the
hh.ru API shape and is mapped into a ``Vacancy`` with company, region, salary,
and publication date. Policy, freshness, localization, and SQLite dedup are
applied downstream by the shared publish pipeline; this module never filters
by policy itself.
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

ZP_API_URL = "https://api.zarplata.ru/vacancies"
ZP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0 Safari/537.36",
    "Accept": "application/json",
}

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


class ZarplataApiAdapter(SourceAdapter):
    name = "Зарплата.ру"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch(self) -> list[Vacancy]:
        queries = _split_queries(self.settings.zp_api_query)
        wanted = max(self.settings.zp_api_results_wanted, 0)
        if wanted <= 0 or not queries:
            return []
        vacancies: list[Vacancy] = []
        seen_urls: set[str] = set()
        async with source_session(headers=ZP_HEADERS) as session:
            for query in queries:
                if len(vacancies) >= wanted:
                    break
                try:
                    payload = await _fetch_zp_api(session, query, wanted)
                    for vacancy in _items_to_vacancies(payload, seen_urls):
                        vacancies.append(vacancy)
                except Exception as exc:
                    # One failing query must not kill the rest of the cycle;
                    # captcha and auth answers are never bypassed.
                    logger.warning("Zarplata.ru fetch failed for %r: %s", query, type(exc).__name__)
        return filter_fresh_vacancies(
            vacancies,
            max_age_hours=self.settings.source_max_age_hours,
            current_time=utcnow(),
            require_published_at=False,
        )


def _split_queries(raw_query: str) -> tuple[str, ...]:
    return tuple(query.strip() for query in raw_query.split("||") if query.strip())


async def _fetch_zp_api(session, query: str, per_page: int) -> Any:
    async with session.get(
        ZP_API_URL,
        params={
            "text": query,
            "per_page": min(max(per_page, 1), 100),
            "page": 0,
        },
    ) as response:
        response.raise_for_status()
        return await response.json()


def _items_to_vacancies(payload: Any, seen_urls: set[str]) -> list[Vacancy]:
    if not isinstance(payload, dict):
        return []
    if "errors" in payload:
        raise ValueError(f"Zarplata.ru API error: {payload.get('errors')}")
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
        if published_at is None:
            published_at = parse_source_datetime(item.get("created_at"))
        raw_text = f"{title}\n{description}"

        vacancies.append(
            Vacancy(
                title=title,
                description=description,
                source=ZarplataApiAdapter.name,
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
