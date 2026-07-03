from __future__ import annotations

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.parser import extract_stack

from ..base import SourceAdapter, html_to_text, source_session


class JoobleAdapter(SourceAdapter):
    name = "Jooble"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch(self) -> list[Vacancy]:
        url = f"https://jooble.org/api/{self.settings.jooble_api_key}"
        payload = {
            "keywords": self.settings.jooble_keywords,
            "location": self.settings.jooble_location,
        }
        async with source_session() as session:
            async with session.post(url, json=payload) as response:
                response.raise_for_status()
                data = await response.json()

        vacancies: list[Vacancy] = []
        for item in data.get("jobs", [])[:80]:
            description = html_to_text(item.get("snippet") or item.get("description") or "")
            vacancies.append(
                Vacancy(
                    title=item.get("title") or "IT Vacancy",
                    company=item.get("company"),
                    location=item.get("location"),
                    description=description,
                    source=self.name,
                    url=item.get("link"),
                    salary=item.get("salary"),
                    stack=extract_stack(" ".join([item.get("title", ""), description])),
                    raw_text=description,
                )
            )
        return vacancies
