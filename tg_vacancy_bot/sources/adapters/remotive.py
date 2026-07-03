from __future__ import annotations

import aiohttp

from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.parser import extract_stack

from ..base import REQUEST_TIMEOUT, SourceAdapter, html_to_text


class RemotiveAdapter(SourceAdapter):
    name = "Remotive"
    url = "https://remotive.com/api/remote-jobs?category=software-dev"

    async def fetch(self) -> list[Vacancy]:
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.get(self.url) as response:
                response.raise_for_status()
                data = await response.json()

        result = []
        for item in data.get("jobs", [])[:80]:
            description = html_to_text(item.get("description", ""))
            result.append(
                Vacancy(
                    title=item.get("title") or "IT Vacancy",
                    company=item.get("company_name"),
                    location=item.get("candidate_required_location") or "Remote",
                    description=description,
                    source=self.name,
                    url=item.get("url"),
                    stack=extract_stack(" ".join([item.get("title", ""), description])),
                    raw_text=description,
                )
            )
        return result
