from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.sources.base import SourceAdapter, source_session
from tg_vacancy_bot.sources.adapters.linkedin_post_headless import (
    BROWSER_HEADERS,
    POST_READ_DELAY_SECONDS,
    POST_READ_RETRY_DELAY_SECONDS,
    _alternate_post_url,
    _canonicalize_linkedin_post_url,
    _discover_free_post_urls,
    _jittered_seconds,
    _read_public_post_http,
)
from tg_vacancy_bot.sources.adapters.linkedin_post_search import (
    LinkedInPostCandidate,
    _candidate_to_vacancy,
)
from tg_vacancy_bot.sources.freshness import filter_fresh_vacancies


def utcnow() -> datetime:
    return datetime.now(UTC)


class LinkedInPostGuestAdapter(SourceAdapter):
    """Discovers public LinkedIn posts and reads them through plain guest HTTP.

    No login, no keyed search provider, and no browser: post discovery reuses
    the same free public search providers as the rest of the LinkedIn pipeline,
    and every post is read through LinkedIn's ordinary public guest route. A
    protection screen, a login wall, or missing post text yields no vacancy.
    """

    name = "LinkedIn Posts (Guest)"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch(self) -> list[Vacancy]:
        limit = max(self.settings.linkedin_post_guest_results_wanted, 0)
        if not limit:
            return []
        candidates = await _discover_free_post_urls(self.settings, limit)
        vacancies: list[Vacancy] = []
        pending: list[LinkedInPostCandidate] = []
        if candidates:
            async with source_session(headers=BROWSER_HEADERS) as session:
                for index, candidate in enumerate(candidates):
                    if index:
                        # Sequential guest reads without pauses are the main
                        # rate-limit trigger; jitter avoids a fixed rhythm.
                        await asyncio.sleep(_jittered_seconds(POST_READ_DELAY_SECONDS))
                    vacancy = await self._read_public_post(session, candidate.url)
                    if vacancy is None:
                        pending.append(candidate)
                    else:
                        vacancies.append(vacancy)
        for candidate in pending:
            # The public search result that discovered the link remains a real,
            # dated source for the same post, so it is used instead of dropping
            # the vacancy.
            vacancy = _snippet_vacancy(candidate)
            if vacancy is not None:
                vacancies.append(vacancy)
        return filter_fresh_vacancies(
            vacancies,
            max_age_hours=self.settings.linkedin_post_max_age_hours,
            current_time=utcnow(),
            require_published_at=True,
        )

    async def _read_public_post(self, session, url: str) -> Vacancy | None:
        """Read one public guest post, retrying its feed-update form once."""

        vacancy = await _read_public_post_http(session, url, source=self.name)
        if vacancy is None:
            alternate = _alternate_post_url(url)
            if alternate:
                await asyncio.sleep(POST_READ_RETRY_DELAY_SECONDS)
                vacancy = await _read_public_post_http(session, alternate, source=self.name)
        return vacancy


def _snippet_vacancy(candidate: LinkedInPostCandidate) -> Vacancy | None:
    vacancy = _candidate_to_vacancy(candidate)
    if vacancy is not None:
        vacancy = replace(vacancy, source=LinkedInPostGuestAdapter.name)
    return vacancy