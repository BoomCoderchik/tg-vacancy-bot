from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.sources.base import SourceAdapter
from tg_vacancy_bot.sources.dates import parse_source_datetime


class JobSpyLinkedInAdapter(SourceAdapter):
    name = "JobSpy LinkedIn"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch(self) -> list[Vacancy]:
        return await asyncio.to_thread(self._fetch_sync)

    def _fetch_sync(self) -> list[Vacancy]:
        scrape_jobs = _load_scrape_jobs()
        jobs = scrape_jobs(
            site_name="linkedin",
            search_term=self.settings.jobspy_linkedin_query,
            location=self.settings.jobspy_linkedin_location,
            results_wanted=self.settings.jobspy_linkedin_results_wanted,
            hours_old=self.settings.jobspy_linkedin_hours_old,
            is_remote=True,
            linkedin_fetch_description=self.settings.jobspy_linkedin_fetch_description,
            proxies=list(self.settings.jobspy_linkedin_proxies) or None,
            verbose=0,
        )
        vacancies = []
        for record in _records(jobs):
            vacancy = _record_to_vacancy(record, self.settings.jobspy_linkedin_query)
            if vacancy is not None:
                vacancies.append(vacancy)
        return vacancies


def _load_scrape_jobs() -> Callable[..., Any]:
    try:
        from jobspy import scrape_jobs
    except ImportError as exc:
        raise RuntimeError(
            "JobSpy LinkedIn source requires the python-jobspy package. "
            "Install project dependencies with `pip install -e .`."
        ) from exc
    return scrape_jobs


def _records(jobs: Any) -> list[Mapping[str, Any]]:
    if jobs is None:
        return []
    if hasattr(jobs, "to_dict"):
        return [record for record in jobs.to_dict("records") if isinstance(record, Mapping)]
    if isinstance(jobs, Iterable):
        return [record for record in jobs if isinstance(record, Mapping)]
    return []


def _record_to_vacancy(record: Mapping[str, Any], query: str) -> Vacancy | None:
    title = _text(record, "title")
    url = _text(record, "job_url")
    if not title or not url:
        return None
    company = _text(record, "company")
    location = _location(record)
    description = _text(record, "description")
    if not description:
        description = f"LinkedIn job link found by JobSpy for query: {query}."

    return Vacancy(
        title=title,
        company=company,
        location=location,
        description=description,
        source=JobSpyLinkedInAdapter.name,
        url=url,
        stack=_stack(record),
        published_at=parse_source_datetime(_value(record, "date_posted")),
        raw_text=" ".join(part for part in (title, company, location, description) if part),
    )


def _location(record: Mapping[str, Any]) -> str | None:
    location = _text(record, "location")
    if location:
        return location
    parts = [_text(record, "city"), _text(record, "state"), _text(record, "country")]
    joined = ", ".join(part for part in parts if part)
    return joined or None


def _stack(record: Mapping[str, Any]) -> tuple[str, ...]:
    values = ["LinkedIn"]
    if _value(record, "is_remote") is True:
        values.append("Remote")
    job_type = _text(record, "job_type")
    if job_type:
        values.append(job_type)
    emails = _value(record, "emails")
    if isinstance(emails, str) and emails.strip():
        values.append(emails.strip())
    elif isinstance(emails, Iterable):
        values.extend(str(email).strip() for email in emails if str(email).strip())
    return tuple(dict.fromkeys(values))


def _text(record: Mapping[str, Any], key: str) -> str:
    value = _value(record, key)
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "nat"} else text


def _value(record: Mapping[str, Any], key: str) -> Any:
    value = record.get(key)
    try:
        if value != value:
            return None
    except (TypeError, ValueError):
        pass
    return value
