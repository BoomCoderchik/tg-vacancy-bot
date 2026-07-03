from __future__ import annotations

import aiohttp

from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.parser import extract_stack

from ..base import REQUEST_TIMEOUT, SourceAdapter, html_to_text


class ArbeitnowAdapter(SourceAdapter):
    name = "Arbeitnow"
    url = "https://www.arbeitnow.com/api/job-board-api"

    async def fetch(self) -> list[Vacancy]:
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.get(self.url) as response:
                response.raise_for_status()
                data = await response.json()

        result = []
        for item in data.get("data", [])[:80]:
            text = html_to_text(item.get("description", ""))
            tags = tuple(item.get("tags") or ())
            result.append(
                Vacancy(
                    title=item.get("title") or "IT Vacancy",
                    company=item.get("company_name"),
                    location=item.get("location"),
                    description=text,
                    source=self.name,
                    url=item.get("url"),
                    stack=tuple(dict.fromkeys([*tags, *extract_stack(text)])),
                    raw_text=text,
                )
            )
        return result
