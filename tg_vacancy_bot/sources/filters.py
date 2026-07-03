from __future__ import annotations

from collections.abc import Iterable

from tg_vacancy_bot.models import Vacancy


POSITIVE_IT_TERMS = [
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

NEGATIVE_TERMS = ["course", "bootcamp", "курс", "обучение"]


def filter_it_vacancies(vacancies: Iterable[Vacancy]) -> list[Vacancy]:
    return [vacancy for vacancy in vacancies if looks_like_it_vacancy(" ".join([vacancy.title, vacancy.description]))]


def looks_like_it_vacancy(text: str) -> bool:
    lower = text.lower()
    return any(token in lower for token in POSITIVE_IT_TERMS) and not any(token in lower for token in NEGATIVE_TERMS)
