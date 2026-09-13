"""Shared free public search-result pipeline for source adapters.

Pure HTTP/parsing helpers without Telegram, LinkedIn, or store dependencies.
They are used by the LinkedIn scraper and headless adapters today and are the
reusable foundation for future open web source adapters.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from xml.etree import ElementTree
from urllib.parse import parse_qs, unquote, urlparse

from bs4 import BeautifulSoup, Tag

from tg_vacancy_bot.sources.adapters.linkedin_post_search import _clean_title
from tg_vacancy_bot.sources.base import html_to_text


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


@dataclass(frozen=True)
class SearchHtmlResult:
    title: str
    link: str
    snippet: str
    date_text: str = ""


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