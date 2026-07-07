from __future__ import annotations

from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.parser import extract_stack

from ..base import SourceAdapter, html_to_text, source_session
from ..dates import parse_source_datetime


class JobicyAdapter(SourceAdapter):
    name = "Jobicy"
    url = "https://jobicy.com/api/v2/remote-jobs?tag=dev"

    async def fetch(self) -> list[Vacancy]:
        async with source_session() as session:
            async with session.get(self.url) as response:
                response.raise_for_status()
                data = await response.json()

        result = []
        for item in data.get("jobs", [])[:80]:
            description = html_to_text(item.get("jobDescription") or item.get("jobExcerpt") or "")
            salary = _format_salary(item.get("salaryMin"), item.get("salaryMax"))
            result.append(
                Vacancy(
                    title=item.get("jobTitle") or "IT Vacancy",
                    company=item.get("companyName"),
                    location=item.get("jobGeo") or "Remote",
                    description=description,
                    source=self.name,
                    url=item.get("url"),
                    stack=tuple(
                        dict.fromkeys(
                            [
                                *(item.get("jobIndustry") or []),
                                *extract_stack(" ".join([item.get("jobTitle", ""), description])),
                            ]
                        )
                    ),
                    salary=salary,
                    published_at=parse_source_datetime(item.get("pubDate")),
                    raw_text=description,
                )
            )
        return result


def _format_salary(minimum: object, maximum: object) -> str | None:
    if minimum and maximum:
        return f"{minimum}-{maximum}"
    if minimum:
        return str(minimum)
    if maximum:
        return str(maximum)
    return None
