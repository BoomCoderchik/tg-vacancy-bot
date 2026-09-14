"""HeadHunter RSS vacancy feed adapter.

Reads the official public HeadHunter RSS feed (``https://hh.ru/search/vacancy/rss``),
which needs no API token, account, or CAPTCHA handling. Queries are plain
full-text search strings split by the ``||`` separator, matching the other
Russia sources. Each RSS item is mapped into a ``Vacancy`` with company,
region, salary, and publication date extracted from the feed description.
Policy, freshness, localization, and SQLite dedup are applied downstream by the
shared publish pipeline; this module never filters by policy itself.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from xml.etree import ElementTree

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.sources.base import SourceAdapter, html_to_text, source_session
from tg_vacancy_bot.sources.dates import parse_source_datetime
from tg_vacancy_bot.sources.freshness import filter_fresh_vacancies

logger = logging.getLogger(__name__)

HH_RSS_URL = "https://hh.ru/search/vacancy/rss"
HH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

# HeadHunter's RSS description is a fixed "label: value" sequence:
#   "Вакансия компании: X Создана: DD.MM.YYYY Регион: Y ППред... дохода: Z"
_COMPANY_PATTERN = re.compile(r"Вакансия компании:\s*(.*?)\s+Создана:", re.S)
_CREATED_PATTERN = re.compile(r"Создана:\s*([\d.]+)", re.S)
_REGION_PATTERN = re.compile(r"Регион:\s*(.*?)\s+Предполагаемый уровень месячного дохода:", re.S)
_SALARY_PATTERN = re.compile(r"Предполагаемый уровень месячного дохода:\s*(.*?)\s*$", re.S)
_NONBREAKING_SPACE_PATTERN = re.compile(r"\s+")


def utcnow() -> datetime:
    return datetime.now(UTC)


class HeadHunterRssAdapter(SourceAdapter):
    name = "HeadHunter RSS"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch(self) -> list[Vacancy]:
        queries = _hh_queries(self.settings.hhru_rss_query)
        wanted = max(self.settings.hhru_rss_results_wanted, 0)
        if wanted <= 0 or not queries:
            return []
        vacancies: list[Vacancy] = []
        seen_urls: set[str] = set()
        async with source_session(headers=HH_HEADERS) as session:
            for query in queries:
                if len(vacancies) >= wanted:
                    break
                try:
                    rss = await _fetch_hh_rss(session, query, wanted)
                    for vacancy in _rss_items_to_vacancies(rss, seen_urls):
                        vacancies.append(vacancy)
                except Exception as exc:
                    # One failing query must not kill the rest of the cycle.
                    logger.warning("HeadHunter RSS fetch failed for %r: %s", query, type(exc).__name__)
        return filter_fresh_vacancies(
            vacancies,
            max_age_hours=self.settings.source_max_age_hours,
            current_time=utcnow(),
            require_published_at=False,
        )


def _hh_queries(raw_query: str) -> tuple[str, ...]:
    return tuple(query.strip() for query in raw_query.split("||") if query.strip())


async def _fetch_hh_rss(session, query: str, per_page: int) -> str:
    async with session.get(
        HH_RSS_URL,
        params={"text": query, "per_page": max(per_page, 1)},
    ) as response:
        response.raise_for_status()
        return await response.text()


def _rss_items_to_vacancies(rss: str, seen_urls: set[str]) -> list[Vacancy]:
    if not (rss or "").strip():
        return []
    try:
        root = ElementTree.fromstring(rss)
    except ElementTree.ParseError:
        return []

    vacancies: list[Vacancy] = []
    for item in root.findall(".//item"):
        url = (item.findtext("link") or item.findtext("guid") or "").strip()
        if not url or url in seen_urls:
            continue
        title = (item.findtext("title") or "").strip()
        description = html_to_text(item.findtext("description") or "")
        if not title or not description:
            continue

        seen_urls.add(url)
        company = _first_match_group(_COMPANY_PATTERN, description)
        region = _first_match_group(_REGION_PATTERN, description)
        salary = _first_match_group(_SALARY_PATTERN, description)
        if salary == "не указан":
            salary = None
        published_at = _published_at_for_item(item, description)
        raw_text = f"{title}\n{description}"

        vacancies.append(
            Vacancy(
                title=title,
                description=description,
                source=HeadHunterRssAdapter.name,
                url=url,
                company=company,
                location=region,
                salary=salary,
                stack=(),
                published_at=published_at,
                raw_text=raw_text,
            )
        )
    return vacancies


def _first_match_group(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    if match is None:
        return None
    value = _NONBREAKING_SPACE_PATTERN.sub(" ", match.group(1)).strip()
    return value or None


def _published_at_for_item(item: ElementTree.Element, description: str) -> datetime | None:
    pub_date = item.findtext("pubDate")
    parsed = parse_source_datetime(pub_date)
    if parsed is not None:
        return parsed
    created = _first_match_group(_CREATED_PATTERN, description)
    if created:
        parsed = parse_source_datetime(created)
        if parsed is not None:
            return parsed
    return None