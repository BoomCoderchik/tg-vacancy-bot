from __future__ import annotations

import asyncio
import logging
import random
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
    ACTIVITY_ID_PATTERN,
    BING_SEARCH_URL,
    BROWSER_HEADERS,
    SearchHtmlResult,
    _clean_title,
    _decode_bing_redirect_url,
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
    _candidate_to_vacancy,
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
# Guest pages sometimes answer a canonical /posts/ URL with a login redirect
# while the feed-update form of the same activity stays publicly readable.
POST_READ_RETRY_DELAY_SECONDS = 2.0
RATE_LIMIT_RETRY_DELAY_SECONDS = 5.0
RETRYABLE_POST_STATUSES = frozenset({429, 999})
HEADLESS_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
# A real-Chrome UA combined with Playwright's default automation flag is an
# inconsistent fingerprint that gets polite public reads classified as bot
# traffic. Disabling the blink automation feature keeps the fingerprint
# consistent with the claimed user agent. No login, cookies, or CAPTCHA
# handling is involved.
CHROMIUM_LAUNCH_ARGS = ("--disable-blink-features=AutomationControlled",)
POST_READ_DELAY_SECONDS = 2.5
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
WAIT_CONTENT_SELECTOR = ", ".join(POST_TEXT_SELECTORS[:4])
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


def _jittered_seconds(base: float) -> float:
    """Return a politeness delay with up to 50% jitter to avoid fixed rhythms."""

    return base + random.uniform(0, base * 0.5)


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
        candidates = await self._discover_keyed_post_urls(limit)
        if not candidates:
            candidates = await self._discover_free_post_urls(limit)

        vacancies: list[Vacancy] = []
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=True,
                args=list(CHROMIUM_LAUNCH_ARGS),
            )
            context = await browser.new_context(
                locale="en-US",
                user_agent=HEADLESS_USER_AGENT,
                viewport={"width": 1366, "height": 768},
            )
            try:
                if not candidates:
                    candidates = await self._discover_browser_post_urls(context, limit)
                for index, candidate in enumerate(candidates):
                    if index:
                        # Sequential guest reads without pauses are the main
                        # rate-limit trigger; jitter avoids a fixed rhythm.
                        await asyncio.sleep(_jittered_seconds(POST_READ_DELAY_SECONDS))
                    vacancy = await self._read_public_post(context, candidate.url, timeout_ms)
                    if vacancy is None:
                        # Direct guest reading can still be refused by a login
                        # wall. The public search result that discovered the
                        # link remains a real, dated source for the same post,
                        # so it is used as the description instead of dropping
                        # the vacancy.
                        vacancy = _candidate_to_vacancy(candidate)
                        if vacancy is not None:
                            vacancy = replace(vacancy, source=self.name)
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

    async def _discover_keyed_post_urls(self, limit: int) -> tuple[LinkedInPostCandidate, ...]:
        provider_types = []
        if self.settings.serpapi_api_key:
            provider_types.append(LinkedInPostSearchAdapter)

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
        return tuple(prioritized[:limit])

    async def _discover_free_post_urls(self, limit: int) -> tuple[LinkedInPostCandidate, ...]:
        """Discover public post URLs without a keyed search provider.

        Lightweight HTTP providers are used for discovery: Bing RSS, DuckDuckGo
        HTML, then paginated Bing HTML, DuckDuckGo Lite, and Mojeek. The
        browser is reserved for reading LinkedIn post pages themselves. A
        protection screen ends that provider's attempt instead of being
        bypassed. Undated results stay in the queue: the reader later derives
        a reliable date from the activity ID or rejects the candidate.
        """

        if limit <= 0:
            return ()
        intents = select_cycle_intents(
            select_search_intents(self.settings.linkedin_post_headless_query),
            max_intents=self.settings.linkedin_post_search_intents_per_cycle,
            cycle_index=_search_cycle_index(utcnow()),
        )
        seen_urls: set[str] = set()
        dated: list[tuple[datetime, LinkedInPostCandidate]] = []
        undated: list[LinkedInPostCandidate] = []

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
                    provider="bing_rss",
                    query=intent,
                    seen_urls=seen_urls,
                    dated=dated,
                    undated=undated,
                    limit=limit,
                )

                await asyncio.sleep(_jittered_seconds(SEARCH_PAGE_DELAY_SECONDS))
                html = await _fetch_provider_html(session, "duckduckgo", intent.query)
                if html:
                    _collect_search_results(
                        _search_html_results(BeautifulSoup(html, "html.parser")),
                        provider="duckduckgo",
                        query=intent,
                        seen_urls=seen_urls,
                        dated=dated,
                        undated=undated,
                        limit=limit,
                    )

                for page_index in range(max(1, self.settings.linkedin_headless_discovery_pages)):
                    if len(seen_urls) >= limit:
                        break
                    await asyncio.sleep(_jittered_seconds(SEARCH_PAGE_DELAY_SECONDS))
                    html = await _fetch_bing_html(session, intent.query, first=1 + page_index * BING_PAGE_STEP)
                    if not html or _looks_like_search_challenge(html):
                        break
                    before = len(seen_urls)
                    _collect_search_results(
                        _search_html_results(BeautifulSoup(html, "html.parser")),
                        provider="bing",
                        query=intent,
                        seen_urls=seen_urls,
                        dated=dated,
                        undated=undated,
                        limit=limit,
                    )
                    if len(seen_urls) == before:
                        break

                for provider in ("duckduckgo_lite", "mojeek"):
                    if len(seen_urls) >= limit:
                        break
                    await asyncio.sleep(_jittered_seconds(SEARCH_PAGE_DELAY_SECONDS))
                    html = await _fetch_provider_html(session, provider, intent.query)
                    if not html:
                        continue
                    _collect_search_results(
                        _search_html_results(BeautifulSoup(html, "html.parser")),
                        provider=provider,
                        query=intent,
                        seen_urls=seen_urls,
                        dated=dated,
                        undated=undated,
                        limit=limit,
                    )

        return tuple(_ordered_discovered_candidates(dated, undated)[:limit])

    async def _discover_browser_post_urls(self, context, limit: int) -> tuple[LinkedInPostCandidate, ...]:
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
        dated: list[tuple[datetime, LinkedInPostCandidate]] = []
        undated: list[LinkedInPostCandidate] = []
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
                        provider="bing_browser",
                        query=intent,
                        seen_urls=seen_urls,
                        dated=dated,
                        undated=undated,
                        limit=limit,
                    )
                    if len(seen_urls) == before:
                        break
                    await asyncio.sleep(_jittered_seconds(SEARCH_PAGE_DELAY_SECONDS))
        finally:
            await page.close()
        return tuple(_ordered_discovered_candidates(dated, undated)[:limit])

    async def _read_public_post(self, context, url: str, timeout_ms: int) -> Vacancy | None:
        page = await context.new_page()
        page.set_default_timeout(timeout_ms)
        try:
            vacancy = await self._read_once(page, url, timeout_ms)
            if vacancy is None:
                # A login/authwall redirect can serve one canonical URL form
                # while the feed-update form of the same activity stays publicly
                # readable. Retry once through that alternate form.
                alternate = _alternate_post_url(url)
                if alternate:
                    await asyncio.sleep(POST_READ_RETRY_DELAY_SECONDS)
                    vacancy = await self._read_once(page, alternate, timeout_ms)
            return vacancy
        finally:
            await page.close()

    async def _read_once(self, page, url: str, timeout_ms: int) -> Vacancy | None:
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            status = getattr(response, "status", None)
            if status in RETRYABLE_POST_STATUSES:
                logger.warning(
                    "LinkedIn post read got HTTP %s; retrying once after backoff", status
                )
                await asyncio.sleep(RATE_LIMIT_RETRY_DELAY_SECONDS)
                response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        except Exception as exc:
            logger.warning("LinkedIn post read failed: %s", type(exc).__name__)
            return None
        final_url = _canonicalize_linkedin_post_url(page.url)
        if not final_url:
            return None
        html = await page.content()
        if _requires_manual_access(html):
            return None
        description = _extract_post_text(html)
        if not description:
            description = await _wait_for_post_text(page, timeout_ms)
        if not description:
            return None
        published_at = _published_at_from_activity_id(final_url)
        if published_at is None:
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
    provider: str,
    query,
    seen_urls: set[str],
    dated: list[tuple[datetime, LinkedInPostCandidate]],
    undated: list[LinkedInPostCandidate],
    limit: int,
) -> None:
    for result in results:
        if len(seen_urls) >= limit:
            return
        url = _canonicalize_linkedin_post_url(_decode_bing_redirect_url(result.link))
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        candidate = LinkedInPostCandidate(
            url=url,
            search_title=result.title,
            snippet=result.snippet,
            date_text=result.date_text,
            provider=provider,
            query=query.query,
            family=query.family,
            language=query.language,
        )
        published_at = _published_at_for_result(result.date_text, url)
        if published_at is None:
            undated.append(candidate)
        else:
            dated.append((published_at, candidate))


def _ordered_discovered_candidates(
    dated: list[tuple[datetime, LinkedInPostCandidate]],
    undated: list[LinkedInPostCandidate],
) -> list[LinkedInPostCandidate]:
    ordered = [candidate for _, candidate in sorted(dated, key=lambda item: (item[0], item[1].url), reverse=True)]
    ordered_set = {candidate.url for candidate in ordered}
    ordered.extend(candidate for candidate in undated if candidate.url not in ordered_set)
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


def _alternate_post_url(url: str) -> str:
    """Return the guest-accessible feed-update form of a LinkedIn post URL.

    Only the ``/posts/`` form can be converted: the reverse mapping would need
    the post slug that only search results provide. Returns an empty string
    when the URL carries no activity ID.
    """

    if "/posts/" not in url:
        return ""
    match = ACTIVITY_ID_PATTERN.search(url)
    if not match:
        return ""
    return f"https://www.linkedin.com/feed/update/urn:li:activity:{match.group(1)}/"


async def _wait_for_post_text(page, timeout_ms: int) -> str:
    """Wait briefly for late-hydrating guest post text; empty on timeout."""

    try:
        await page.wait_for_selector(WAIT_CONTENT_SELECTOR, state="attached", timeout=timeout_ms)
    except Exception as exc:
        logger.warning("LinkedIn post text did not render in time: %s", type(exc).__name__)
        return ""
    return _extract_post_text(await page.content())


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
