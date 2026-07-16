from __future__ import annotations

from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.parser import extract_stack

from ..base import SourceAdapter, html_to_text, source_session
from ..dates import parse_source_datetime


class WorkingNomadsAdapter(SourceAdapter):
    """Reads the public Working Nomads JSON feed without an account or API key."""

    name = "Working Nomads"
    url = "https://www.workingnomads.com/api/exposed_jobs/"

    async def fetch(self) -> list[Vacancy]:
        async with source_session() as session:
            async with session.get(self.url) as response:
                response.raise_for_status()
                data = await response.json()

        if not isinstance(data, list):
            raise RuntimeError("Working Nomads API returned an invalid response.")

        result = []
        for item in data[:100]:
            if not isinstance(item, dict):
                continue
            vacancy_url = _optional_text(item.get("url"))
            if not vacancy_url:
                continue
            text = html_to_text(str(item.get("description") or ""))
            tags = tuple(tag.strip() for tag in str(item.get("tags") or "").split(",") if tag.strip())
            result.append(
                Vacancy(
                    title=str(item.get("title") or "IT Vacancy"),
                    company=_optional_text(item.get("company_name")),
                    location=_optional_text(item.get("location")),
                    description=text,
                    source=self.name,
                    url=vacancy_url,
                    stack=tuple(dict.fromkeys([*tags, *extract_stack(text)])),
                    published_at=parse_source_datetime(item.get("pub_date")),
                    raw_text=text,
                )
            )
        return result


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None
