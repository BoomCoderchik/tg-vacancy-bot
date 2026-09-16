"""SuperJob public API vacancy adapter.

Reads the official SuperJob API v2 vacancy search
(``https://api.superjob.ru/2.0/vacancies/``). A free registered application key
rides in the ``X-Api-App-Id`` header; vacancy contacts are never requested, so
no user authorization is involved and the adapter registers only when
``SUPERJOB_API_KEY`` is set. Each object is mapped into a ``Vacancy`` with
company, town, salary, and unixtime publication date. Policy, freshness,
localization, and SQLite dedup are applied downstream by the shared publish
pipeline; this module never filters by policy itself.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.sources.base import SourceAdapter, html_to_text, source_session
from tg_vacancy_bot.sources.freshness import filter_fresh_vacancies

logger = logging.getLogger(__name__)

SUPERJOB_API_URL = "https://api.superjob.ru/2.0/vacancies/"

_CURRENCY_SYMBOLS = {
    "rub": "\u20bd",
    "uah": "\u20b4",
    "uzs": "сум",
}


def utcnow() -> datetime:
    return datetime.now(UTC)


class SuperJobApiAdapter(SourceAdapter):
    name = "SuperJob"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch(self) -> list[Vacancy]:
        api_key = self.settings.superjob_api_key.strip()
        queries = _split_queries(self.settings.superjob_api_query)
        wanted = max(self.settings.superjob_api_results_wanted, 0)
        if wanted <= 0 or not queries or not api_key:
            if self.settings.enable_superjob_api and not api_key:
                logger.warning("SuperJob fetch skipped: SUPERJOB_API_KEY is empty.")
            return []
        headers = {
            "X-Api-App-Id": api_key,
            "Accept": "application/json",
        }
        vacancies: list[Vacancy] = []
        seen_urls: set[str] = set()
        async with source_session(headers=headers) as session:
            for query in queries:
                if len(vacancies) >= wanted:
                    break
                try:
                    payload = await _fetch_superjob_api(session, query, wanted)
                    for vacancy in _items_to_vacancies(payload, seen_urls):
                        vacancies.append(vacancy)
                except Exception as exc:
                    # One failing query must not kill the rest of the cycle.
                    logger.warning("SuperJob fetch failed for %r: %s", query, type(exc).__name__)
        return filter_fresh_vacancies(
            vacancies,
            max_age_hours=self.settings.source_max_age_hours,
            current_time=utcnow(),
            require_published_at=False,
        )


def _split_queries(raw_query: str) -> tuple[str, ...]:
    return tuple(query.strip() for query in raw_query.split("||") if query.strip())


async def _fetch_superjob_api(session, query: str, per_page: int) -> Any:
    async with session.get(
        SUPERJOB_API_URL,
        params={
            "keyword": query,
            "order_field": "date",
            "order_direction": "desc",
            "count": min(max(per_page, 1), 100),
            "page": 0,
        },
    ) as response:
        response.raise_for_status()
        return await response.json()


def _items_to_vacancies(payload: Any, seen_urls: set[str]) -> list[Vacancy]:
    if not isinstance(payload, dict):
        return []
    if "error" in payload:
        raise ValueError(f"SuperJob API error: {payload.get('error')}")
    objects = payload.get("objects")
    if not isinstance(objects, list):
        return []

    vacancies: list[Vacancy] = []
    for item in objects:
        if not isinstance(item, dict):
            continue
        title = str(item.get("profession") or "").strip()
        url = str(item.get("link") or "").strip()
        if not title or not url or url in seen_urls:
            continue
        seen_urls.add(url)
        town = item.get("town") or {}
        description = _compose_description(item)
        if not description:
            continue
        salary = _format_salary(item)
        published_at = _published_at(item.get("date_published"))
        raw_text = f"{title}\n{description}"

        vacancies.append(
            Vacancy(
                title=title,
                description=description,
                source=SuperJobApiAdapter.name,
                url=url,
                company=str(item.get("firm_name") or "").strip() or None,
                location=str(town.get("title") or "").strip() or None,
                salary=salary,
                stack=(),
                published_at=published_at,
                raw_text=raw_text,
            )
        )
    return vacancies


def _compose_description(item: dict) -> str:
    parts = [
        html_to_text(str(item.get("work") or "")),
        html_to_text(str(item.get("candidat") or "")),
        html_to_text(str(item.get("compensation") or "")),
    ]
    return "\n\n".join(part.strip() for part in parts if part.strip())


def _format_salary(item: dict) -> str | None:
    currency = str(item.get("currency") or "").strip().lower()
    symbol = _CURRENCY_SYMBOLS.get(currency, str(item.get("currency") or "").strip() or None)
    parts = []
    if item.get("payment_from"):
        parts.append(f"от {item.get('payment_from')}")
    if item.get("payment_to"):
        parts.append(f"до {item.get('payment_to')}")
    if not parts:
        return None
    text = " ".join(parts)
    if symbol:
        text = f"{text} {symbol}"
    return text


def _published_at(value: Any) -> datetime | None:
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return None
    if timestamp <= 0:
        return None
    return datetime.fromtimestamp(timestamp, tz=UTC)
