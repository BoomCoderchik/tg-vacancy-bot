from __future__ import annotations

from abc import ABC, abstractmethod

import aiohttp
from bs4 import BeautifulSoup

from tg_vacancy_bot.models import Vacancy


REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=20)


class SourceAdapter(ABC):
    name: str

    @abstractmethod
    async def fetch(self) -> list[Vacancy]:
        raise NotImplementedError


def html_to_text(value: str) -> str:
    soup = BeautifulSoup(value or "", "html.parser")
    return " ".join(soup.get_text(" ").split())
