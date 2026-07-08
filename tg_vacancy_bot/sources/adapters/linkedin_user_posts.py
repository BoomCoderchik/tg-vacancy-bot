from __future__ import annotations

from datetime import UTC, datetime

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.linkedin_posts import (
    build_linkedin_user_post_vacancy,
    extract_linkedin_user_post_records,
)
from tg_vacancy_bot.models import Vacancy

from ..base import SourceAdapter, source_session


class LinkedInUserPostsAdapter(SourceAdapter):
    name = "LinkedIn user posts"

    def __init__(self, settings: Settings) -> None:
        self.feed_url = settings.linkedin_user_posts_feed_url
        self.max_age_hours = settings.source_max_age_hours

    async def fetch(self) -> list[Vacancy]:
        async with source_session() as session:
            async with session.get(self.feed_url) as response:
                response.raise_for_status()
                payload = await response.json()

        records = extract_linkedin_user_post_records(payload)
        now = datetime.now(UTC)
        vacancies = [
            build_linkedin_user_post_vacancy(record, now=now, max_age_hours=self.max_age_hours)
            for record in records
        ]
        return [vacancy for vacancy in vacancies if vacancy is not None]
