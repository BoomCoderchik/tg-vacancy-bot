from __future__ import annotations

import logging
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.sources.base import SourceAdapter, html_to_text
from tg_vacancy_bot.sources.adapters.linkedin_post_scraper import _published_at_from_activity_id
from tg_vacancy_bot.sources.adapters.linkedin_post_search import (
    LinkedInPostCandidate,
    LinkedInPostSearchAdapter,
    LinkedInPostSerperAdapter,
    _canonicalize_linkedin_post_url,
    _published_at_for_result,
    _post_title,
    _stack_from_text,
)
from tg_vacancy_bot.sources.freshness import filter_fresh_vacancies
from tg_vacancy_bot.sources.linkedin_search_profile import (
    fair_query_limits,
    select_cycle_intents,
    select_search_intents,
)


BING_SEARCH_URL = "https://www.bing.com/search"
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
            urls = await self._discover_bing_post_urls(limit, timeout_ms)
        if not urls:
            return []

        vacancies: list[Vacancy] = []
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(locale="en-US")
            try:
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

    async def _discover_bing_post_urls(self, limit: int, timeout_ms: int) -> tuple[str, ...]:
        urls: list[str] = []
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(locale="en-US")
            try:
                search_page = await context.new_page()
                search_page.set_default_timeout(timeout_ms)
                all_intents = select_search_intents(self.settings.linkedin_post_headless_query)
                intents = select_cycle_intents(
                    all_intents,
                    max_intents=self.settings.linkedin_post_search_intents_per_cycle,
                    cycle_index=_search_cycle_index(utcnow()),
                )
                for intent in intents:
                    for url in await _search_public_post_urls(search_page, intent.query):
                        if url not in urls:
                            urls.append(url)
                        if len(urls) >= limit:
                            return tuple(urls)
            finally:
                await context.close()
                await browser.close()
        return tuple(urls)

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


async def _search_public_post_urls(page, query: str) -> tuple[str, ...]:
    search_url = f"{BING_SEARCH_URL}?{urlencode({'q': query, 'setlang': 'en'})}"
    await page.goto(search_url, wait_until="domcontentloaded")
    html = await page.content()
    if _requires_manual_access(html):
        return ()
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    for anchor in soup.select("li.b_algo h2 a[href], a[href*='linkedin.com/posts/'], a[href*='linkedin.com/feed/update/']"):
        href = str(anchor.get("href") or "").strip()
        canonical = _canonicalize_linkedin_post_url(href)
        if canonical and canonical not in urls:
            urls.append(canonical)
    return tuple(urls)


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
