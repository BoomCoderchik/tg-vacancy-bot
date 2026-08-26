from __future__ import annotations

import asyncio
import base64
import logging
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlsplit
from xml.etree import ElementTree

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.sources.base import SourceAdapter, html_to_text, source_session
from tg_vacancy_bot.sources.adapters.linkedin_post_scraper import (
    BING_SEARCH_URL,
    BROWSER_HEADERS,
    SearchHtmlResult,
    _clean_title,
    _fetch_bing_rss,
    _fetch_search_html,
    _looks_like_search_challenge,
    _published_at_for_result,
    _published_at_from_activity_id,
    _search_html_results,
    _xml_child_text,
)
from tg_vacancy_bot.sources.adapters.linkedin_post_search import (
    LinkedInPostCandidate,
    LinkedInPostSearchAdapter,
    LinkedInPostSerperAdapter,
    _canonicalize_linkedin_post_url,
    _post_title,
    _stack_from_text,
)
from tg_vacancy_bot.sources.freshness import filter_fresh_vacancies
from tg_vacancy_bot.sources.linkedin_search_profile import (
    fair_query_limits,
    select_cycle_intents,
    select_search_intents,
)


BING_PAGE_STEP = 10
SEARCH_PAGE_DELAY_SECONDS = 1.5
logger = logging.getLogger(__name__)
POST_TEXT_SELECTORS = (
    "article p.attributed-text-segment-list__content",
    "article [class*='attributed-text-segment-list__content']",
    "p.attributed-text-segment-list__content",
    "[class*='attributed-text-segment-list__content']",
    ".feed-shared-update-v2__description-wrapper",
    ".feed-shared-inline-show-more-text",
    "[data-test-id*='commentary']",
)
PROTECTION_MARKERS = (
    "captcha to continue",
    "complete the captcha",
    "verify you are human",
    "unusual traffic",
    "security check",
    "two-factor",
    "2fa",
)


def utcnow() -> datetime:
    return datetime.now(UTC)


class LinkedInPostHeadlessAdapter(SourceAdapter):
    """Reads public LinkedIn post pages without login or anti-bot bypassing."""

    name = "LinkedIn Hiring Posts (Headless)"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch(self) -> list[Vacancy]:
        if not (
            self.settings.linkedin_headless_access_authorized
            and self.settings.linkedin_headless_permission_reference.strip()
        ):
            return []
        limit = max(self.settings.linkedin_post_headless_results_wanted, 0)
        if not limit:
            return []

        timeout_ms = self.settings.linkedin_post_headless_timeout_seconds * 1000
        urls = await self._discover_keyed_post_urls(limit)
        if not urls:
            urls = await self._discover_free_post_urls(limit)

        vacancies: list[Vacancy] = []
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(locale="en-US")
            try:
                if not urls:
                    urls = await self._discover_browser_post_urls(context, limit)
                for url in urls:
                    vacancy = await self._read_public_post(context, url, timeout_ms)
                    if vacancy is not None:
                        vacancies.append(vacancy)
            finally:
                await context.close()
                await browser.close()
        return filter_fresh_vacancies(
            vacancies,
            max_age_hours=self.settings.linkedin_post_max_age_hours,
            current_time=utcnow(),
            require_published_at=True,
        )

    async def _discover_keyed_post_urls(self, limit: int) -> tuple[str, ...]:
        provider_types = []
        if self.settings.serpapi_api_key:
            provider_types.append(LinkedInPostSearchAdapter)
        if self.settings.serper_api_key:
            provider_types.append(LinkedInPostSerperAdapter)

        current_time = utcnow()
        all_intents = select_search_intents(self.settings.linkedin_post_headless_query)
        intents = select_cycle_intents(
            all_intents,
            max_intents=self.settings.linkedin_post_search_intents_per_cycle,
            cycle_index=_search_cycle_index(current_time),
        )
        discovery_budget = max(limit, len(intents))
        query_limits = fair_query_limits(discovery_budget, intents)
        candidates: list[LinkedInPostCandidate] = []
        seen_urls: set[str] = set()
        for intent, query_limit in zip(intents, query_limits, strict=True):
            if query_limit <= 0:
                continue
            search_settings = self.settings.model_copy(
                update={
                    "linkedin_post_search_query": intent.query,
                    "linkedin_post_search_results_wanted": query_limit,
                }
            )
            for provider_type in provider_types:
                provider = provider_type(search_settings)
                try:
                    discovered = await provider.discover(limit=query_limit)
                except Exception as exc:
                    logger.warning("%s discovery failed: %s", provider.name, type(exc).__name__)
                    continue
                new_for_intent = 0
                for position, candidate in enumerate(discovered, start=1):
                    if candidate.url in seen_urls:
                        continue
                    seen_urls.add(candidate.url)
                    candidates.append(
                        replace(
                            candidate,
                            family=intent.family,
                            language=intent.language,
                            position=candidate.position or position,
                        )
                    )
                    new_for_intent += 1
                if new_for_intent:
                    break
        prioritized = sorted(
            candidates,
            key=lambda candidate: _candidate_priority_key(
                candidate,
                current_time=current_time,
                max_age_hours=self.settings.linkedin_post_max_age_hours,
            ),
            reverse=True,
        )
        return _post_urls_from_candidates(prioritized, limit)

    async def _discover_free_post_urls(self, limit: int) -> tuple[str, ...]:
        """Discover public post URLs without a keyed search provider.

        Lightweight HTTP providers are used for discovery: Bing RSS, DuckDuckGo
        HTML, then paginated Bing HTML. The browser is reserved for reading
        LinkedIn post pages themselves. A protection screen ends that
        provider's attempt instead of being bypassed. Undated results stay in
        the queue: the reader later derives a reliable date from the activity
        ID or rejects the candidate.
        """

        if limit <= 0:
            return ()
        intents = select_cycle_intents(
            select_search_intents(self.settings.linkedin_post_headless_query),
            max_intents=self.settings.linkedin_post_search_intents_per_cycle,
            cycle_index=_search_cycle_index(utcnow()),
        )
        seen_urls: set[str] = set()
        dated_urls: list[tuple[datetime, str]] = []
        undated_urls: list[str] = []

        async with source_session(headers=BROWSER_HEADERS) as session:
            for intent in intents:
                if len(seen_urls) >= limit:
                    break

                try:
                    rss_results = _rss_post_results(await _fetch_bing_rss(session, intent.query))
                except Exception as exc:
                    logger.warning("Bing RSS discovery failed: %s", type(exc).__name__)
                    rss_results = []
                _collect_search_results(
                    rss_results,
                    seen_urls=seen_urls,
                    dated_urls=dated_urls,
                    undated_urls=undated_urls,
                    limit=limit,
                )

                await asyncio.sleep(SEARCH_PAGE_DELAY_SECONDS)
                html = await _fetch_provider_html(session, "duckduckgo", intent.query)
                if html:
                    _collect_search_results(
                        _search_html_results(BeautifulSoup(html, "html.parser")),
                        seen_urls=seen_urls,
                        dated_urls=dated_urls,
                        undated_urls=undated_urls,
                        limit=limit,
                    )

                for page_index in range(max(1, self.settings.linkedin_headless_discovery_pages)):
                    if len(seen_urls) >= limit:
                        break
                    await asyncio.sleep(SEARCH_PAGE_DELAY_SECONDS)
                    html = await _fetch_bing_html(session, intent.query, first=1 + page_index * BING_PAGE_STEP)
                    if not html or _looks_like_search_challenge(html):
                        break
                    before = len(seen_urls)
                    _collect_search_results(
                        _search_html_results(BeautifulSoup(html, "html.parser")),
                        seen_urls=seen_urls,
                        dated_urls=dated_urls,
                        undated_urls=undated_urls,
                        limit=limit,
                    )
                    if len(seen_urls) == before:
                        break

        return tuple(_ordered_discovered_urls(dated_urls, undated_urls)[:limit])

    async def _discover_browser_post_urls(self, context, limit: int) -> tuple[str, ...]:
        """Discover public post URLs by reading Bing result pages in a browser.

        Used when keyed and lightweight HTTP discovery produced no candidates.
        The same clean headless context that reads LinkedIn posts performs the
        searches. A protection screen or an unexpected redirect domain ends
        the current attempt instead of being bypassed.
        """

        if limit <= 0:
            return ()
        intents = select_cycle_intents(
            select_search_intents(self.settings.linkedin_post_headless_query),
            max_intents=self.settings.linkedin_post_search_intents_per_cycle,
            cycle_index=_search_cycle_index(utcnow()),
        )
        timeout_ms = self.settings.linkedin_post_headless_timeout_seconds * 1000
        seen_urls: set[str] = set()
        dated_urls: list[tuple[datetime, str]] = []
        undated_urls: list[str] = []
        page = await context.new_page()
        page.set_default_timeout(timeout_ms)
        try:
            for intent in intents:
                if len(seen_urls) >= limit:
                    break
                for page_index in range(max(1, self.settings.linkedin_headless_discovery_pages)):
                    html = await _fetch_bing_result_html(
                        page,
                        intent.query,
                        first=1 + page_index * BING_PAGE_STEP,
                    )
                    if not html:
                        break
                    before = len(seen_urls)
                    _collect_search_results(
                        _search_html_results(BeautifulSoup(html, "html.parser")),
                        seen_urls=seen_urls,
                        dated_urls=dated_urls,
                        undated_urls=undated_urls,
                        limit=limit,
                    )
                    if len(seen_urls) == before:
                        break
                    await asyncio.sleep(SEARCH_PAGE_DELAY_SECONDS)
        finally:
            await page.close()
        return tuple(_ordered_discovered_urls(dated_urls, undated_urls)[:limit])

    async def _read_public_post(self, context, url: str, timeout_ms: int) -> Vacancy | None:
        page = await context.new_page()
        page.set_default_timeout(timeout_ms)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            final_url = _canonicalize_linkedin_post_url(page.url)
            if not final_url:
                return None
            html = await page.content()
            if _requires_manual_access(html):
                return None
            description = _extract_post_text(html)
            published_at = _published_at_from_activity_id(final_url)
            if not description or published_at is None:
                return None
            title = _post_title(await page.title(), description)
            if not title:
                return None
            return Vacancy(
                title=title,
                description=description,
                source=self.name,
                url=final_url,
                location=None,
                stack=_stack_from_text(f"{title} {description}"),
                published_at=published_at,
                raw_text=f"{title} {description}",
            )
        finally:
            await page.close()


async def _fetch_provider_html(session, provider: str, query: str) -> str:
    """Fetch one search-result page; a protection screen yields no results."""

    try:
        html = await _fetch_search_html(session, provider, query)
    except Exception as exc:
        logger.warning("%s discovery fetch failed: %s", provider, type(exc).__name__)
        return ""
    if _looks_like_search_challenge(html):
        logger.warning("%s discovery returned an anti-bot challenge; skipping", provider)
        return ""
    return html


async def _fetch_bing_result_html(page, query: str, *, first: int) -> str:
    """Read one Bing result page in the browser context; failure yields no results."""

    url = f"{BING_SEARCH_URL}?{urlencode({'q': query, 'first': str(first), 'setlang': 'en'})}"
    try:
        await page.goto(url, wait_until="domcontentloaded")
        host = (urlsplit(page.url).hostname or "").lower()
        if host not in {"bing.com", "www.bing.com", "cn.bing.com"}:
            logger.warning("Bing browser discovery redirected off-domain (%s); skipping", host or "unknown")
            return ""
        html = await page.content()
    except Exception as exc:
        logger.warning("Bing browser discovery fetch failed: %s", type(exc).__name__)
        return ""
    if _looks_like_search_challenge(html):
        logger.warning("Bing browser discovery returned an anti-bot challenge; skipping")
        return ""
    return html


def _collect_search_results(
    results: list[SearchHtmlResult],
    *,
    seen_urls: set[str],
    dated_urls: list[tuple[datetime, str]],
    undated_urls: list[str],
    limit: int,
) -> None:
    for result in results:
        if len(seen_urls) >= limit:
            return
        url = _canonicalize_linkedin_post_url(_decode_bing_redirect_url(result.link))
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        published_at = _published_at_for_result(result.date_text, url)
        if published_at is None:
            undated_urls.append(url)
        else:
            dated_urls.append((published_at, url))


def _ordered_discovered_urls(
    dated_urls: list[tuple[datetime, str]],
    undated_urls: list[str],
) -> list[str]:
    ordered = [url for _, url in sorted(dated_urls, reverse=True)]
    ordered_set = set(ordered)
    ordered.extend(url for url in undated_urls if url not in ordered_set)
    return ordered


async def _fetch_bing_html(session, query: str, *, first: int) -> str:
    try:
        async with session.get(
            BING_SEARCH_URL,
            params={"q": query, "first": str(first), "setlang": "en"},
        ) as response:
            response.raise_for_status()
            return await response.text()
    except Exception as exc:
        logger.warning("Bing HTML discovery fetch failed: %s", type(exc).__name__)
        return ""


def _rss_post_results(rss: str) -> list[SearchHtmlResult]:
    """Keep raw RSS items as URL candidates even without title or snippet."""

    if not (rss or "").strip():
        return []
    try:
        root = ElementTree.fromstring(rss)
    except ElementTree.ParseError:
        return []
    results: list[SearchHtmlResult] = []
    for item in root.findall(".//item"):
        results.append(
            SearchHtmlResult(
                title=_clean_title(_xml_child_text(item, "title")),
                link=_xml_child_text(item, "link"),
                snippet="",
                date_text=_xml_child_text(item, "pubDate"),
            )
        )
    return results


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


def _post_urls_from_candidates(
    candidates: list[LinkedInPostCandidate],
    limit: int,
) -> tuple[str, ...]:
    urls: list[str] = []
    for candidate in candidates:
        if candidate.url and candidate.url not in urls:
            urls.append(candidate.url)
        if len(urls) >= limit:
            break
    return tuple(urls)


def _candidate_priority_key(
    candidate: LinkedInPostCandidate,
    *,
    current_time: datetime,
    max_age_hours: int,
) -> tuple[int, datetime]:
    published_at = _published_at_for_result(candidate.date_text, candidate.url)
    if published_at is None:
        return (1, datetime.min.replace(tzinfo=UTC))
    cutoff = current_time - timedelta(hours=max_age_hours)
    return (2 if published_at >= cutoff else 0, published_at)


def _search_cycle_index(current_time: datetime) -> int:
    return int(current_time.timestamp() // (15 * 60))


def _extract_post_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for selector in POST_TEXT_SELECTORS:
        for node in soup.select(selector):
            text = html_to_text(str(node))
            if text:
                return text[:4000]
    return ""


def _requires_manual_access(html: str) -> bool:
    soup = BeautifulSoup(html or "", "html.parser")
    text = html_to_text(str(soup)).lower()
    if any(marker in text for marker in PROTECTION_MARKERS):
        return True
    # Public post pages include a sign-in form in the navigation. Treat a
    # password input as a login wall only when the page exposes no post text.
    return soup.select_one("input[type='password']") is not None and not _extract_post_text(html)
