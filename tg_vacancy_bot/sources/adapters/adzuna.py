from __future__ import annotations

import aiohttp

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.parser import extract_stack

from ..base import REQUEST_TIMEOUT, SourceAdapter, html_to_text


class AdzunaAdapter(SourceAdapter):
    name = "Adzuna"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch(self) -> list[Vacancy]:
        country = self.settings.adzuna_country.strip().lower() or "us"
        url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
        params = {
            "app_id": self.settings.adzuna_app_id,
            "app_key": self.settings.adzuna_app_key,
            "what": self.settings.adzuna_query,
            "results_per_page": "50",
            "content-type": "application/json",
        }
        if self.settings.adzuna_location:
            params["where"] = self.settings.adzuna_location

        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()

        vacancies: list[Vacancy] = []
        for item in data.get("results", []):
            description = html_to_text(item.get("description", ""))
            company = item.get("company") or {}
            location = item.get("location") or {}
            area = location.get("area") or []
            vacancies.append(
                Vacancy(
                    title=item.get("title") or "IT Vacancy",
                    company=company.get("display_name"),
                    location=", ".join(area) if area else location.get("display_name"),
                    description=description,
                    source=self.name,
                    url=item.get("redirect_url"),
                    salary=_format_adzuna_salary(item),
                    stack=extract_stack(" ".join([item.get("title", ""), description])),
                    raw_text=description,
                )
            )
        return vacancies


def _format_adzuna_salary(item: dict) -> str | None:
    min_salary = item.get("salary_min")
    max_salary = item.get("salary_max")
    if not min_salary and not max_salary:
        return None
    if min_salary and max_salary:
        return f"{int(min_salary):,} - {int(max_salary):,}".replace(",", " ")
    return str(int(min_salary or max_salary))
