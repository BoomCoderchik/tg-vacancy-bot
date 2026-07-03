from __future__ import annotations

from abc import ABC, abstractmethod

import aiohttp
from bs4 import BeautifulSoup

from tg_vacancy_bot.models import Vacancy


REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=20)
DEFAULT_HEADERS = {"User-Agent": "TG Vacancy Bot/0.1 (+https://t.me)"}


class SourceAdapter(ABC):
    name: str

    @abstractmethod
    async def fetch(self) -> list[Vacancy]:
        raise NotImplementedError


def html_to_text(value: str) -> str:
    soup = BeautifulSoup(value or "", "html.parser")
    return " ".join(soup.get_text(" ").split())


def source_session(**kwargs) -> aiohttp.ClientSession:
    headers = {**DEFAULT_HEADERS, **kwargs.pop("headers", {})}
    return aiohttp.ClientSession(timeout=REQUEST_TIMEOUT, headers=headers, **kwargs)
