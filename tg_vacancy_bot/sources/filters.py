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

NEGATIVE_TERMS = [
    "course",
    "bootcamp",
    "cleaner",
    "janitor",
    "office manager",
    "sales",
    "marketing",
    "support",
    "driver",
    "courier",
    "recruiter",
    "hr manager",
    "account manager",
    "customer success",
    "курс",
    "обучение",
    "уборщик",
    "уборщица",
    "офис-менеджер",
    "офис менеджер",
    "продажи",
    "маркетинг",
    "поддержка",
    "водитель",
    "курьер",
    "рекрутер",
]


DEVELOPMENT_ROLE_TERMS = [
    "backend",
    "back-end",
    "back end",
    "frontend",
    "front-end",
    "front end",
    "fullstack",
    "full-stack",
    "full stack",
    "designer",
    "design",
    "ui/ux",
    "ux/ui",
    "llm",
    "ai engineer",
    "ai developer",
    "ai/ml engineer",
    "ml engineer",
    "machine learning engineer",
    "machine learning developer",
    "artificial intelligence engineer",
    "artificial intelligence developer",
    "developer",
    "software engineer",
    "python engineer",
    "python developer",
    "java engineer",
    "java developer",
    "go engineer",
    "go developer",
    "golang engineer",
    "golang developer",
    "node.js engineer",
    "node.js developer",
    "react engineer",
    "react developer",
    "vue engineer",
    "vue developer",
    "angular engineer",
    "angular developer",
    "typescript engineer",
    "typescript developer",
    "javascript engineer",
    "javascript developer",
    "разработчик",
    "программист",
    "backend-разработчик",
    "frontend-разработчик",
    "фронтенд",
    "бэкенд",
    "машинное обучение",
    "ml-инженер",
    "ai-инженер",
]


def filter_it_vacancies(vacancies: Iterable[Vacancy]) -> list[Vacancy]:
    return [
        vacancy
        for vacancy in vacancies
        if looks_like_development_vacancy(" ".join([vacancy.title, vacancy.description]))
    ]


def looks_like_it_vacancy(text: str) -> bool:
    lower = text.lower()
    return any(token in lower for token in POSITIVE_IT_TERMS) and not any(token in lower for token in NEGATIVE_TERMS)


def looks_like_development_vacancy(text: str) -> bool:
    lower = text.lower()
    return any(token in lower for token in DEVELOPMENT_ROLE_TERMS) and not any(
        token in lower for token in NEGATIVE_TERMS
    )
