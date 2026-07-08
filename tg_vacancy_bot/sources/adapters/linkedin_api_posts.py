from __future__ import annotations

from datetime import UTC, datetime

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.linkedin_posts import build_linkedin_user_post_vacancy
from tg_vacancy_bot.models import Vacancy

from ..base import SourceAdapter, source_session


LINKEDIN_POSTS_API_URL = "https://api.linkedin.com/rest/posts"


class LinkedInApiPostsAdapter(SourceAdapter):
    name = "LinkedIn Posts API"

    def __init__(self, settings: Settings) -> None:
        self.access_token = settings.linkedin_api_access_token
        self.author_urns = settings.linkedin_api_author_urns
        self.api_version = settings.linkedin_api_version
        self.max_age_hours = settings.source_max_age_hours

    async def fetch(self) -> list[Vacancy]:
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "LinkedIn-Version": self.api_version,
            "X-RestLi-Method": "FINDER",
            "X-Restli-Protocol-Version": "2.0.0",
        }
        now = datetime.now(UTC)
        vacancies: list[Vacancy] = []
        async with source_session(headers=headers) as session:
            for author_urn in self.author_urns:
                async with session.get(
                    LINKEDIN_POSTS_API_URL,
                    params={
                        "q": "author",
                        "author": author_urn,
                        "count": "20",
                        "sortBy": "LAST_MODIFIED",
                    },
                ) as response:
                    response.raise_for_status()
                    payload = await response.json()
                for item in _extract_post_items(payload):
                    record = _post_item_to_record(item)
                    vacancy = build_linkedin_user_post_vacancy(
                        record,
                        now=now,
                        max_age_hours=self.max_age_hours,
                    )
                    if vacancy:
                        vacancies.append(vacancy)
        return vacancies


def _extract_post_items(payload: object) -> list[dict[str, object]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        elements = payload.get("elements")
        if isinstance(elements, list):
            return [item for item in elements if isinstance(item, dict)]
    return []


def _post_item_to_record(item: dict[str, object]) -> dict[str, object]:
    post_id = _first_text(item, "id", "entity")
    return {
        "url": _first_text(item, "url", "permalink") or _post_url(post_id),
        "text": _first_text(item, "commentary", "text", "content", "summary"),
        "published_at": item.get("publishedAt")
        or item.get("createdAt")
        or item.get("lastModifiedAt")
        or item.get("created"),
        "author": _first_text(item, "author"),
    }


def _first_text(record: dict[str, object], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())
    return ""


def _post_url(post_id: str) -> str:
    if not post_id:
        return ""
    return f"https://www.linkedin.com/feed/update/{post_id}/"
