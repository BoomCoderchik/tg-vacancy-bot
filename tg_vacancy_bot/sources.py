from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

import aiohttp
from bs4 import BeautifulSoup

from .config import Settings
from .models import Vacancy
from .parser import extract_stack


REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=20)


class SourceAdapter(ABC):
    name: str

    @abstractmethod
    async def fetch(self) -> list[Vacancy]:
        raise NotImplementedError


def html_to_text(value: str) -> str:
    soup = BeautifulSoup(value or "", "html.parser")
    return " ".join(soup.get_text(" ").split())


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


class RemoteOkAdapter(SourceAdapter):
    name = "RemoteOK"
    url = "https://remoteok.com/api"

    async def fetch(self) -> list[Vacancy]:
        headers = {"User-Agent": "TG Vacancy Bot/0.1 (+https://t.me)"}
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT, headers=headers) as session:
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


class HackerNewsWhoIsHiringAdapter(SourceAdapter):
    name = "Hacker News"
    feed_url = "https://hnrss.org/item?id=1"

    async def fetch(self) -> list[Vacancy]:
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.get("https://hn.algolia.com/api/v1/search_by_date?tags=story&query=who%20is%20hiring") as response:
                response.raise_for_status()
                data = await response.json()

        story = next((item for item in data.get("hits", []) if _is_current_hiring_thread(item.get("title", ""))), None)
        if not story:
            return []

        story_id = story["objectID"]
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.get(f"https://hn.algolia.com/api/v1/items/{story_id}") as response:
                response.raise_for_status()
                thread = await response.json()

        vacancies: list[Vacancy] = []
        for child in thread.get("children", [])[:120]:
            text = html_to_text(child.get("text") or "")
            if not text or not _looks_like_it_vacancy(text):
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


def build_adapters(settings: Settings) -> list[SourceAdapter]:
    adapters: list[SourceAdapter] = []
    if settings.enable_remotive:
        adapters.append(RemotiveAdapter())
    if settings.enable_arbeitnow:
        adapters.append(ArbeitnowAdapter())
    if settings.enable_remoteok:
        adapters.append(RemoteOkAdapter())
    if settings.enable_hn_who_is_hiring:
        adapters.append(HackerNewsWhoIsHiringAdapter())
    return adapters


def filter_it_vacancies(vacancies: Iterable[Vacancy]) -> list[Vacancy]:
    return [vacancy for vacancy in vacancies if _looks_like_it_vacancy(" ".join([vacancy.title, vacancy.description]))]


def _format_remoteok_salary(item: dict) -> str | None:
    min_salary = item.get("salary_min")
    max_salary = item.get("salary_max")
    if not min_salary and not max_salary:
        return None
    if min_salary and max_salary:
        return f"${min_salary} - ${max_salary}"
    return f"${min_salary or max_salary}"


def _is_current_hiring_thread(title: str) -> bool:
    title = title.lower()
    return "who is hiring" in title and "freelancer" not in title


def _looks_like_it_vacancy(text: str) -> bool:
    lower = text.lower()
    positive = [
        "developer",
        "engineer",
        "software",
        "backend",
        "frontend",
        "full stack",
        "devops",
        "data scientist",
        "machine learning",
        "python",
        "javascript",
        "typescript",
        "react",
        "разработчик",
        "инженер",
        "программист",
    ]
    negative = ["course", "bootcamp", "курс", "обучение"]
    return any(token in lower for token in positive) and not any(token in lower for token in negative)
