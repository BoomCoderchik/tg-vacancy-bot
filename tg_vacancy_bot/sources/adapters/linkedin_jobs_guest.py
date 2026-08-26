from __future__ import annotations

import asyncio
import logging
import random
import re
from datetime import UTC, datetime

from bs4 import BeautifulSoup

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.sources.base import SourceAdapter, html_to_text, source_session
from tg_vacancy_bot.sources.adapters.linkedin_post_scraper import BROWSER_HEADERS
from tg_vacancy_bot.sources.dates import parse_source_datetime
from tg_vacancy_bot.sources.freshness import filter_fresh_vacancies


logger = logging.getLogger(__name__)

JOBS_GUEST_SEARCH_URL = (
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
)
JOBS_GUEST_HEADERS = {
    **BROWSER_HEADERS,
    "Accept-Language": "en-US,en;q=0.9",
}
PAGE_SIZE = 10
SEARCH_PAGE_DELAY_SECONDS = 1.5
JOB_READ_DELAY_SECONDS = 2.5

JUNIOR_TITLE_RE = re.compile(
    r"(?<!\w)(juniors?|jr\.?|interns?\b|internship|trainees?|graduate\b|entry[\s-]?level)",
    re.IGNORECASE,
)
ROLE_TITLE_RE = re.compile(
    r"\bfront[\s-]?ends?\b|\bfrontends?\b|\bfull[\s-]?stacks?\b|\bфронтенд\w*|\bфул[\s-]?стек\w*",
    re.IGNORECASE,
)

DESCRIPTION_SELECTORS = (
    "div.show-more-less-html__markup",
    "section.show-more-less-html",
)


def utcnow() -> datetime:
    return datetime.now(UTC)


def _jittered_seconds(base: float) -> float:
    return base + random.uniform(0, base * 0.5)


class LinkedInJobsGuestAdapter(SourceAdapter):
    """Reads LinkedIn's own public, logged-out job listings.

    The guest job-search endpoint and public job pages need no account, no
    cookies, and no protection bypass; requests are paced politely. This is
    the discovery path that keeps working when third-party search engines
    block datacenter or flagged IPs.
    """

    name = "LinkedIn Jobs (Guest)"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch(self) -> list[Vacancy]:
        limit = max(self.settings.linkedin_jobs_guest_results_wanted, 0)
        if not limit:
            return []
        max_age_hours = self.settings.linkedin_post_max_age_hours
        tpr_seconds = max_age_hours * 3600
        keywords = self.settings.linkedin_jobs_guest_keywords

        vacancies: list[Vacancy] = []
        seen_urls: set[str] = set()
        async with source_session(headers=JOBS_GUEST_HEADERS) as session:
            for keyword in keywords:
                if len(seen_urls) >= limit:
                    break
                for start in range(0, limit, PAGE_SIZE):
                    cards = await self._search_cards(session, keyword, tpr_seconds, start)
                    if not cards:
                        break
                    await asyncio.sleep(_jittered_seconds(SEARCH_PAGE_DELAY_SECONDS))
                    for card in cards:
                        if card.url in seen_urls:
                            continue
                        if len(seen_urls) >= limit:
                            break
                        seen_urls.add(card.url)
                        vacancy = await self._read_job(session, card)
                        if vacancy is not None:
                            vacancies.append(vacancy)
                        if len(seen_urls) >= limit:
                            break
        return filter_fresh_vacancies(
            vacancies,
            max_age_hours=max_age_hours,
            current_time=utcnow(),
            require_published_at=True,
        )

    async def _search_cards(
        self,
        session,
        keyword: str,
        tpr_seconds: int,
        start: int,
    ) -> list[_GuestJobCard]:
        try:
            async with session.get(
                JOBS_GUEST_SEARCH_URL,
                params={
                    "keywords": keyword,
                    "f_TPR": f"r{tpr_seconds}",
                    "start": str(start),
                },
            ) as response:
                response.raise_for_status()
                html = await response.text()
        except Exception as exc:
            logger.warning("Jobs guest search failed: %s", type(exc).__name__)
            return []
        return parse_guest_job_cards(html, keyword=keyword)

    async def _read_job(self, session, card: _GuestJobCard) -> Vacancy | None:
        await asyncio.sleep(_jittered_seconds(JOB_READ_DELAY_SECONDS))
        description = await self._fetch_description(session, card.url)
        title_parts = [card.title]
        if card.company:
            title_parts.append(f"at {card.company}")
        title = " ".join(title_parts)
        fallback_text = f"Posted {card.posted_date:%Y-%m-%d}." if card.posted_date else ""
        description_text = description or fallback_text
        location_part = f" Location: {card.location}." if card.location else ""
        raw_text = f"{title}.{location_part} {description_text}".strip()
        return Vacancy(
            title=title,
            description=description_text[:4000],
            source=self.name,
            url=card.url,
            location=card.location or None,
            stack=("LinkedIn job",),
            published_at=card.posted_date,
            raw_text=raw_text[:6000],
        )

    async def _fetch_description(self, session, url: str) -> str:
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.warning("Job page read got HTTP %s", response.status)
                    return ""
                html = await response.text()
        except Exception as exc:
            logger.warning("Job page read failed: %s", type(exc).__name__)
            return ""
        soup = BeautifulSoup(html, "html.parser")
        for selector in DESCRIPTION_SELECTORS:
            node = soup.select_one(selector)
            if node is not None:
                text = " ".join(node.get_text(" ").split())[:4000]
                if text:
                    return text
        return ""


class _GuestJobCard:
    __slots__ = ("url", "title", "company", "location", "posted_date")

    def __init__(
        self,
        url: str,
        title: str,
        company: str,
        location: str,
        posted_date: datetime | None,
    ) -> None:
        self.url = url
        self.title = title
        self.company = company
        self.location = location
        self.posted_date = posted_date


def parse_guest_job_cards(html: str, *, keyword: str = "") -> list[_GuestJobCard]:
    """Parse one guest search-result page into candidate cards.

    Only titles that already carry junior-level and frontend/fullstack
    evidence are kept, so page reads are spent on plausible vacancies.
    """

    soup = BeautifulSoup(html or "", "html.parser")
    cards: list[_GuestJobCard] = []
    for card_node in soup.select("li"):
        if not hasattr(card_node, "select_one"):
            continue
        anchor = card_node.select_one("a.base-card__full-link")
        title_el = card_node.select_one("h3.base-search-card__title")
        if anchor is None or title_el is None:
            continue
        title = html_to_text(str(title_el))
        url = str(anchor.get("href") or "").split("?")[0]
        if not url or "/jobs/view/" not in url:
            continue
        if not (JUNIOR_TITLE_RE.search(title) and ROLE_TITLE_RE.search(title)):
            continue
        company_el = card_node.select_one("h4.base-search-card__subtitle")
        location_el = card_node.select_one(".job-search-card__location")
        time_el = card_node.select_one("time")
        posted = parse_source_datetime(str(time_el.get("datetime"))) if time_el is not None else None
        cards.append(
            _GuestJobCard(
                url=url,
                title=title,
                company=html_to_text(str(company_el)) if company_el is not None else "",
                location=html_to_text(str(location_el)) if location_el is not None else "",
                posted_date=posted,
            )
        )
    return cards
