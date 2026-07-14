from __future__ import annotations

from urllib.parse import urlencode

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.sources.base import SourceAdapter, html_to_text
from tg_vacancy_bot.sources.adapters.linkedin_post_scraper import _published_at_from_activity_id
from tg_vacancy_bot.sources.adapters.linkedin_post_search import (
    LinkedInPostSearchAdapter,
    LinkedInPostSerperAdapter,
    _is_linkedin_post_url,
    _post_title,
    _search_queries,
    _stack_from_text,
)


BING_SEARCH_URL = "https://www.bing.com/search"
POST_TEXT_SELECTORS = (
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


class LinkedInPostHeadlessAdapter(SourceAdapter):
    """Reads public LinkedIn post pages without login or anti-bot bypassing."""

    name = "LinkedIn Hiring Posts (Headless)"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch(self) -> list[Vacancy]:
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
            context = await browser.new_context(locale="ru-RU")
            try:
                for url in urls:
                    vacancy = await self._read_public_post(context, url, timeout_ms)
                    if vacancy is not None:
                        vacancies.append(vacancy)
            finally:
                await context.close()
                await browser.close()
        return vacancies

    async def _discover_keyed_post_urls(self, limit: int) -> tuple[str, ...]:
        search_settings = self.settings.model_copy(
            update={
                "linkedin_post_search_query": self.settings.linkedin_post_headless_query,
                "linkedin_post_search_location": self.settings.linkedin_post_headless_location,
                "linkedin_post_search_results_wanted": limit,
            }
        )
        providers = []
        if self.settings.serpapi_api_key:
            providers.append(LinkedInPostSearchAdapter(search_settings))
        if self.settings.serper_api_key:
            providers.append(LinkedInPostSerperAdapter(search_settings))

        for provider in providers:
            urls = _post_urls_from_vacancies(await provider.fetch(), limit)
            if urls:
                return urls
        return ()

    async def _discover_bing_post_urls(self, limit: int, timeout_ms: int) -> tuple[str, ...]:
        urls: list[str] = []
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(locale="ru-RU")
            try:
                search_page = await context.new_page()
                search_page.set_default_timeout(timeout_ms)
                for query in _search_queries(self.settings.linkedin_post_headless_query):
                    for url in await _search_public_post_urls(search_page, query):
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
            html = await page.content()
            if _requires_manual_access(html):
                return None
            description = _extract_post_text(html)
            published_at = _published_at_from_activity_id(url)
            if not description or published_at is None:
                return None
            title = _post_title(await page.title(), description)
            if not title:
                return None
            return Vacancy(
                title=title,
                description=description,
                source=self.name,
                url=url,
                location=self.settings.linkedin_post_headless_location or None,
                stack=_stack_from_text(f"{title} {description}"),
                published_at=published_at,
                raw_text=f"{title} {description}",
            )
        finally:
            await page.close()


async def _search_public_post_urls(page, query: str) -> tuple[str, ...]:
    search_url = f"{BING_SEARCH_URL}?{urlencode({'q': query, 'setlang': 'ru'})}"
    await page.goto(search_url, wait_until="domcontentloaded")
    html = await page.content()
    if _requires_manual_access(html):
        return ()
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    for anchor in soup.select("li.b_algo h2 a[href], a[href*='linkedin.com/posts/'], a[href*='linkedin.com/feed/update/']"):
        href = str(anchor.get("href") or "").strip()
        if href and _is_linkedin_post_url(href) and href not in urls:
            urls.append(href)
    return tuple(urls)


def _post_urls_from_vacancies(vacancies: list[Vacancy], limit: int) -> tuple[str, ...]:
    urls: list[str] = []
    for vacancy in vacancies:
        url = (vacancy.url or "").strip()
        if url and _is_linkedin_post_url(url) and url not in urls:
            urls.append(url)
        if len(urls) >= limit:
            break
    return tuple(urls)


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
