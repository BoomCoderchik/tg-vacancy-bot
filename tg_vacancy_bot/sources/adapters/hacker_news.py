from __future__ import annotations

from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.parser import extract_stack

from ..base import SourceAdapter, html_to_text, source_session
from ..filters import looks_like_it_vacancy


class HackerNewsWhoIsHiringAdapter(SourceAdapter):
    name = "Hacker News"

    async def fetch(self) -> list[Vacancy]:
        async with source_session() as session:
            async with session.get("https://hn.algolia.com/api/v1/search_by_date?tags=story&query=who%20is%20hiring") as response:
                response.raise_for_status()
                data = await response.json()

        story = next((item for item in data.get("hits", []) if _is_current_hiring_thread(item.get("title", ""))), None)
        if not story:
            return []

        story_id = story["objectID"]
        async with source_session() as session:
            async with session.get(f"https://hn.algolia.com/api/v1/items/{story_id}") as response:
                response.raise_for_status()
                thread = await response.json()

        vacancies: list[Vacancy] = []
        for child in thread.get("children", [])[:120]:
            text = html_to_text(child.get("text") or "")
            if not text or not looks_like_it_vacancy(text):
                continue
            first_part = text.split("|", 1)[0].strip()
            vacancies.append(
                Vacancy(
                    title=first_part[:90] or "HN Who is Hiring",
                    description=text,
                    source=self.name,
                    url=f"https://news.ycombinator.com/item?id={child.get('id')}",
                    location=None,
                    stack=extract_stack(text),
                    raw_text=text,
                )
            )
        return vacancies


def _is_current_hiring_thread(title: str) -> bool:
    title = title.lower()
    return "who is hiring" in title and "freelancer" not in title
