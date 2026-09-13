from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from xml.etree import ElementTree

from bs4 import BeautifulSoup

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.sources.base import SourceAdapter, html_to_text, source_session
from tg_vacancy_bot.sources.freshness import filter_fresh_vacancies
from tg_vacancy_bot.sources.adapters.linkedin_post_search import (
    _clean_title,
    _is_linkedin_post_url,
    _parse_search_date,
    _post_title,
    _search_queries,
    _stack_from_text,
)
from tg_vacancy_bot.sources.search_providers import (
    BING_RSS_SEARCH_URL,
    BING_SEARCH_URL,
    BROWSER_HEADERS,
    DUCKDUCKGO_HTML_SEARCH_URL,
    DUCKDUCKGO_LITE_SEARCH_URL,
    MOJEEK_SEARCH_URL,
    SearchHtmlResult,
    _append_result,
    _date_text_for_container,
    _decode_bing_redirect_url,
    _fetch_bing_rss,
    _fetch_search_html,
    _looks_like_search_challenge,
    _normalize_result_url,
    _search_html_results,
    _snippet_for_anchor,
    _snippet_for_container,
    _xml_child_text,
)


logger = logging.getLogger(__name__)
ACTIVITY_ID_PATTERN = re.compile(r"activity[-:](\d{15,20})(?:[-:/?#]|$)", re.IGNORECASE)


def utcnow() -> datetime:
    return datetime.now(UTC)


class LinkedInPostScraperAdapter(SourceAdapter):
    name = "LinkedIn Hiring Post Scraper"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch(self) -> list[Vacancy]:
        limit = max(self.settings.linkedin_post_scraper_results_wanted, 0)
        vacancies: list[Vacancy] = []
        seen_urls: set[str] = set()
        challenged_providers: set[str] = set()
        failed_providers: set[str] = set()
        attempted_providers: set[str] = set()
        async with source_session(headers=BROWSER_HEADERS) as session:
            for query in _search_queries(self.settings.linkedin_post_scraper_query):
                if len(vacancies) >= limit:
                    break
                for provider in self.settings.linkedin_post_scraper_search_providers:
                    if len(vacancies) >= limit:
                        break
                    attempted_providers.add(provider)
                    try:
                        if provider == "bing_rss":
                            rss = await _fetch_bing_rss(session, query)
                            vacancies.extend(
                                _rss_to_vacancies(
                                    rss,
                                    limit=limit - len(vacancies),
                                    seen_urls=seen_urls,
                                )
                            )
                            continue
                        html = await _fetch_search_html(session, provider, query)
                        if _looks_like_search_challenge(html):
                            challenged_providers.add(provider)
                            continue
                        vacancies.extend(
                            _html_to_vacancies(
                                html,
                                limit=limit - len(vacancies),
                                seen_urls=seen_urls,
                            )
                        )
                    except Exception as exc:
                        # One blocked or failing provider must not kill the whole
                        # polling cycle; the remaining providers still run.
                        failed_providers.add(provider)
                        logger.warning("%s search fetch failed: %s", provider, type(exc).__name__)
        if not vacancies and attempted_providers:
            if challenged_providers | failed_providers == attempted_providers:
                details = []
                if challenged_providers:
                    details.append(
                        "anti-bot challenges: " + ", ".join(sorted(challenged_providers))
                    )
                if failed_providers:
                    details.append("request failures: " + ", ".join(sorted(failed_providers)))
                raise RuntimeError(
                    "Public search providers returned no usable results (" + "; ".join(details) + ")."
                )
        return filter_fresh_vacancies(
            vacancies,
            max_age_hours=self.settings.linkedin_post_max_age_hours,
            current_time=utcnow(),
            require_published_at=True,
        )


def _html_to_vacancies(html: str, limit: int, seen_urls: set[str] | None = None) -> list[Vacancy]:
    soup = BeautifulSoup(html or "", "html.parser")
    vacancies: list[Vacancy] = []
    seen = seen_urls if seen_urls is not None else set()

    for result in _search_html_results(soup):
        vacancy = _result_to_vacancy(result, seen)
        if vacancy is None:
            continue
        vacancies.append(vacancy)
        if len(vacancies) >= limit:
            break
    return vacancies


def _rss_to_vacancies(rss: str, limit: int, seen_urls: set[str] | None = None) -> list[Vacancy]:
    vacancies: list[Vacancy] = []
    seen = seen_urls if seen_urls is not None else set()
    if limit <= 0 or not rss.strip():
        return vacancies

    try:
        root = ElementTree.fromstring(rss)
    except ElementTree.ParseError:
        return vacancies

    for item in root.findall(".//item"):
        result = SearchHtmlResult(
            title=_clean_title(_xml_child_text(item, "title")),
            link=_xml_child_text(item, "link"),
            snippet=html_to_text(_xml_child_text(item, "description")),
            date_text=_xml_child_text(item, "pubDate"),
        )
        vacancy = _result_to_vacancy(result, seen)
        if vacancy is None:
            continue
        vacancies.append(vacancy)
        if len(vacancies) >= limit:
            break
    return vacancies


def _result_to_vacancy(result: SearchHtmlResult, seen: set[str]) -> Vacancy | None:
    search_title = _clean_title(result.title)
    link = _normalize_result_url(result.link)
    if not search_title or not link or not _is_linkedin_post_url(link) or link in seen:
        return None

    snippet = result.snippet
    if not snippet:
        return None
    title = _post_title(search_title, snippet)
    published_at = _published_at_for_result(result.date_text, link)
    if published_at is None:
        # Do not publish an undated result: search engines can return very old
        # indexed LinkedIn posts without exposing their publication date.
        return None

    seen.add(link)
    return Vacancy(
        title=title,
        description=snippet,
        source=LinkedInPostScraperAdapter.name,
        url=link,
        location=None,
        stack=_stack_from_text(f"{title} {snippet} {search_title}"),
        published_at=published_at,
        raw_text=f"{title} {snippet}",
    )


def _published_at_for_result(date_text: str, link: str) -> datetime | None:
    parsed = _parse_search_date(date_text)
    if parsed is not None:
        return parsed
    return _published_at_from_activity_id(link)


def _published_at_from_activity_id(link: str) -> datetime | None:
    match = ACTIVITY_ID_PATTERN.search(link)
    if not match:
        return None
    try:
        # LinkedIn activity IDs use the same 22-bit worker/sequence layout as
        # Snowflake IDs; their high bits are milliseconds since Unix epoch.
        timestamp_ms = int(match.group(1)) >> 22
        return datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)
    except (ValueError, OSError, OverflowError):
        return None
