from __future__ import annotations

import re
from datetime import UTC, datetime
from urllib.parse import parse_qs, unquote, urlparse

from bs4 import BeautifulSoup, Tag

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.sources.base import SourceAdapter, html_to_text, source_session
from tg_vacancy_bot.sources.adapters.linkedin_post_search import (
    _clean_title,
    _is_linkedin_post_url,
    _parse_search_date,
    _post_title,
    _search_queries,
    _stack_from_text,
)


DUCKDUCKGO_HTML_SEARCH_URL = "https://html.duckduckgo.com/html/"
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "ru,en;q=0.8",
}
ACTIVITY_ID_PATTERN = re.compile(r"activity-(\d{15,20})(?:[-/?#]|$)", re.IGNORECASE)


class LinkedInPostScraperAdapter(SourceAdapter):
    name = "LinkedIn Hiring Post Scraper"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch(self) -> list[Vacancy]:
        limit = max(self.settings.linkedin_post_scraper_results_wanted, 0)
        vacancies: list[Vacancy] = []
        seen_urls: set[str] = set()
        async with source_session(headers=BROWSER_HEADERS) as session:
            for query in _search_queries(self.settings.linkedin_post_scraper_query):
                if len(vacancies) >= limit:
                    break
                async with session.get(DUCKDUCKGO_HTML_SEARCH_URL, params={"q": query}) as response:
                    response.raise_for_status()
                    html = await response.text()
                if _looks_like_search_challenge(html):
                    raise RuntimeError("Public search HTML returned an anti-bot challenge.")
                vacancies.extend(
                    _html_to_vacancies(
                        html,
                        location=self.settings.linkedin_post_scraper_location,
                        limit=limit - len(vacancies),
                        seen_urls=seen_urls,
                    )
                )
        return vacancies


def _html_to_vacancies(html: str, location: str, limit: int, seen_urls: set[str] | None = None) -> list[Vacancy]:
    soup = BeautifulSoup(html or "", "html.parser")
    vacancies: list[Vacancy] = []
    seen = seen_urls if seen_urls is not None else set()

    for anchor in soup.select("a.result__a, a.result-link, a[href]"):
        if not isinstance(anchor, Tag):
            continue
        search_title = _clean_title(html_to_text(str(anchor)))
        link = _normalize_result_url(str(anchor.get("href") or ""))
        if not search_title or not link or not _is_linkedin_post_url(link) or link in seen:
            continue

        snippet = _snippet_for_anchor(anchor)
        if not snippet:
            continue
        title = _post_title(search_title, snippet)
        published_at = _published_at_for_result(anchor, link)
        if published_at is None:
            # Do not publish an undated result: search engines can return very
            # old indexed LinkedIn posts without exposing their publication date.
            continue

        seen.add(link)
        vacancies.append(
            Vacancy(
                title=title,
                description=snippet,
                source=LinkedInPostScraperAdapter.name,
                url=link,
                location=location or None,
                stack=_stack_from_text(f"{title} {snippet} {search_title}"),
                published_at=published_at,
                raw_text=f"{title} {snippet}",
            )
        )
        if len(vacancies) >= limit:
            break
    return vacancies

def _looks_like_search_challenge(html: str) -> bool:
    lower = (html or "").lower()
    return "challenge-form" in lower or "anomaly-modal" in lower or "anomaly.js" in lower


def _normalize_result_url(href: str) -> str:
    if not href:
        return ""
    parsed = urlparse(href)
    if parsed.path == "/l/":
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(target).strip()
    if href.startswith("//"):
        return f"https:{href}"
    return href.strip()


def _snippet_for_anchor(anchor: Tag) -> str:
    container = anchor.find_parent(class_="result")
    candidates = []
    if container is not None:
        candidates.extend(container.select(".result__snippet, .result-snippet"))
    next_snippet = anchor.find_next(class_=["result__snippet", "result-snippet"])
    if next_snippet is not None:
        candidates.append(next_snippet)

    for candidate in candidates:
        text = html_to_text(str(candidate))
        if text:
            return text
    return ""


def _published_at_for_result(anchor: Tag, link: str) -> datetime | None:
    container = anchor.find_parent(class_="result")
    if container is not None:
        for candidate in container.select("time, [class*=date], [class*=time]"):
            value = str(candidate.get("datetime") or html_to_text(str(candidate)))
            parsed = _parse_search_date(value)
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
