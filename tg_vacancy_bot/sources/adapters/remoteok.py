from __future__ import annotations

from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.parser import extract_stack

from ..base import SourceAdapter, html_to_text, source_session


class RemoteOkAdapter(SourceAdapter):
    name = "RemoteOK"
    url = "https://remoteok.com/api"

    async def fetch(self) -> list[Vacancy]:
        async with source_session() as session:
            async with session.get(self.url) as response:
                response.raise_for_status()
                data = await response.json(content_type=None)

        result = []
        for item in data[1:81]:
            text = html_to_text(item.get("description") or "")
            tags = tuple(item.get("tags") or ())
            result.append(
                Vacancy(
                    title=item.get("position") or "IT Vacancy",
                    company=item.get("company"),
                    location=item.get("location") or "Remote",
                    description=text or "Remote IT vacancy",
                    source=self.name,
                    url=item.get("url"),
                    stack=tuple(dict.fromkeys([*tags, *extract_stack(text)])),
                    salary=_format_remoteok_salary(item),
                    raw_text=text,
                )
            )
        return result


def _format_remoteok_salary(item: dict) -> str | None:
    min_salary = item.get("salary_min")
    max_salary = item.get("salary_max")
    if not min_salary and not max_salary:
        return None
    if min_salary and max_salary:
        return f"${min_salary} - ${max_salary}"
    return f"${min_salary or max_salary}"
