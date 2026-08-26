from __future__ import annotations

import base64
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from xml.etree import ElementTree
from urllib.parse import parse_qs, unquote, urlparse

from bs4 import BeautifulSoup, Tag

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


logger = logging.getLogger(__name__)
DUCKDUCKGO_HTML_SEARCH_URL = "https://html.duckduckgo.com/html/"
DUCKDUCKGO_LITE_SEARCH_URL = "https://lite.duckduckgo.com/lite/"
MOJEEK_SEARCH_URL = "https://www.mojeek.com/search"
BING_SEARCH_URL = "https://www.bing.com/search"
BING_RSS_SEARCH_URL = "https://www.bing.com/search"
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
ACTIVITY_ID_PATTERN = re.compile(r"activity[-:](\d{15,20})(?:[-:/?#]|$)", re.IGNORECASE)


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class SearchHtmlResult:
    title: str
    link: str
    snippet: str
    date_text: str = ""


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


async def _fetch_search_html(session, provider: str, query: str) -> str:
    if provider == "bing":
        async with session.get(BING_SEARCH_URL, params={"q": query, "setlang": "en"}) as response:
            response.raise_for_status()
            return await response.text()
    if provider == "duckduckgo_lite":
        async with session.get(DUCKDUCKGO_LITE_SEARCH_URL, params={"q": query}) as response:
            response.raise_for_status()
            return await response.text()
    if provider == "mojeek":
        async with session.get(MOJEEK_SEARCH_URL, params={"q": query}) as response:
            response.raise_for_status()
            return await response.text()
    # DuckDuckGo serves the same public HTML form endpoint over POST, while
    # datacenter GET requests to it are regularly answered with an anomaly
    # screen. The POST form is the documented query path of that page.
    async with session.post(DUCKDUCKGO_HTML_SEARCH_URL, data={"q": query}) as response:
        response.raise_for_status()
        return await response.text()


async def _fetch_bing_rss(session, query: str) -> str:
    async with session.get(BING_RSS_SEARCH_URL, params={"q": query, "format": "rss", "setlang": "en"}) as response:
        response.raise_for_status()
        return await response.text()


def _looks_like_search_challenge(html: str) -> bool:
    lower = (html or "").lower()
    return (
        "challenge-form" in lower
        or "anomaly-modal" in lower
        or "anomaly.js" in lower
        or "captcha" in lower
        or "unusual traffic" in lower
        or "automated queries" in lower
    )


def _search_html_results(soup: BeautifulSoup) -> list[SearchHtmlResult]:
    results: list[SearchHtmlResult] = []
    seen_links: set[str] = set()

    for anchor in soup.select("a.result__a, a.result-link"):
        if not isinstance(anchor, Tag):
            continue
        result = SearchHtmlResult(
            title=_clean_title(html_to_text(str(anchor))),
            link=str(anchor.get("href") or ""),
            snippet=_snippet_for_anchor(anchor),
            date_text=_date_text_for_container(anchor.find_parent(class_="result")),
        )
        _append_result(results, seen_links, result)

    for container in soup.select("li.b_algo"):
        if not isinstance(container, Tag):
            continue
        anchor = container.select_one("h2 a[href], a[href]")
        if not isinstance(anchor, Tag):
            continue
        result = SearchHtmlResult(
            title=_clean_title(html_to_text(str(anchor))),
            link=str(anchor.get("href") or ""),
            snippet=_snippet_for_container(container),
            date_text=_date_text_for_container(container),
        )
        _append_result(results, seen_links, result)

    for container in soup.select("ul.results-standard li"):
        # Mojeek result layout: <li><h2><a href>title</a></h2><p class="s">.
        if not isinstance(container, Tag):
            continue
        anchor = container.select_one("h2 a[href], a[href]")
        if not isinstance(anchor, Tag):
            continue
        result = SearchHtmlResult(
            title=_clean_title(html_to_text(str(anchor))),
            link=str(anchor.get("href") or ""),
            snippet=_snippet_for_container(container),
            date_text="",
        )
        _append_result(results, seen_links, result)

    if results:
        return results

    for anchor in soup.select("a[href]"):
        if not isinstance(anchor, Tag):
            continue
        result = SearchHtmlResult(
            title=_clean_title(html_to_text(str(anchor))),
            link=str(anchor.get("href") or ""),
            snippet=_snippet_for_anchor(anchor),
            date_text=_date_text_for_container(anchor.find_parent(class_="result")),
        )
        _append_result(results, seen_links, result)

    return results


def _append_result(results: list[SearchHtmlResult], seen_links: set[str], result: SearchHtmlResult) -> None:
    normalized = _normalize_result_url(result.link)
    if normalized and normalized not in seen_links:
        seen_links.add(normalized)
        results.append(result)


def _normalize_result_url(href: str) -> str:
    if not href:
        return ""
    decoded = _decode_bing_redirect_url(href)
    parsed = urlparse(decoded)
    if parsed.path == "/l/":
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(target).strip()
    if decoded.startswith("//"):
        return f"https:{decoded}"
    return decoded.strip()


def _decode_bing_redirect_url(href: str) -> str:
    """Decode Bing ``/ck/a`` redirect wrappers into the real target URL."""

    if "/ck/a" not in href:
        return href
    marker = "u=a1"
    index = href.find(marker)
    if index == -1:
        return ""
    payload = href[index + len(marker):].split("&", 1)[0]
    padding = "=" * (-len(payload) % 4)
    try:
        return base64.urlsafe_b64decode(payload + padding).decode("utf-8", "ignore")
    except (ValueError, UnicodeDecodeError):
        return ""


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


def _snippet_for_container(container: Tag) -> str:
    for selector in (".b_caption p", ".b_snippet", ".result__snippet", ".result-snippet", "p.s", "p"):
        candidate = container.select_one(selector)
        if candidate is None:
            continue
        text = html_to_text(str(candidate))
        if text:
            return text
    return ""


def _date_text_for_container(container: Tag | None) -> str:
    if container is None:
        return ""
    for candidate in container.select("time, .news_dt, [class*=date], [class*=time]"):
        value = str(candidate.get("datetime") or html_to_text(str(candidate))).strip()
        if value:
            return value
    return ""


def _xml_child_text(item: ElementTree.Element, child_name: str) -> str:
    child = item.find(child_name)
    return "".join(child.itertext()).strip() if child is not None else ""


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
