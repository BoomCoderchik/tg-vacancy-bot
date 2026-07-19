from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


LINKEDIN_POST_SITE_SCOPE = "(site:linkedin.com/posts OR site:linkedin.com/feed/update)"
HIRING_INTENT = {
    "en": '("we are hiring" OR "we\'re hiring" OR "hiring for" OR "looking for" OR "join our team" OR "open role")',
    "ru": '("ищем" OR "ищет" OR "нанимаем" OR "в команду" OR "открыта вакансия")',
}


@dataclass(frozen=True, slots=True)
class SearchIntent:
    """One explicit hiring search for a named vacancy family and language."""

    family: str
    language: str
    query: str


def _intent(family: str, language: str, roles: str) -> SearchIntent:
    return SearchIntent(
        family=family,
        language=language,
        query=f"{LINKEDIN_POST_SITE_SCOPE} {HIRING_INTENT[language]} ({roles})",
    )


DEFAULT_SEARCH_INTENTS: tuple[SearchIntent, ...] = (
    _intent(
        "backend-software",
        "en",
        '"Backend Developer" OR "Backend Engineer" OR "Software Developer" OR "Software Engineer"',
    ),
    _intent(
        "backend-software",
        "ru",
        '"бэкенд-разработчик" OR "backend-разработчик" OR "разработчик ПО" OR "программный инженер"',
    ),
    _intent(
        "frontend",
        "en",
        '"Frontend Developer" OR "Front-End Developer" OR "Frontend Engineer" OR "Front-End Engineer"',
    ),
    _intent(
        "frontend",
        "ru",
        '"фронтенд-разработчик" OR "frontend-разработчик" OR "фронтенд-инженер"',
    ),
    _intent(
        "fullstack",
        "en",
        '"Fullstack Developer" OR "Full-Stack Developer" OR "Fullstack Engineer" OR "Full-Stack Engineer"',
    ),
    _intent(
        "fullstack",
        "ru",
        '"фулстек-разработчик" OR "fullstack-разработчик" OR "фулстек-инженер"',
    ),
    _intent(
        "mobile",
        "en",
        '"Mobile Developer" OR "Mobile Engineer" OR "iOS Developer" OR "Android Developer" OR "Flutter Developer" OR "React Native Developer"',
    ),
    _intent(
        "mobile",
        "ru",
        '"мобильный разработчик" OR "iOS-разработчик" OR "Android-разработчик" OR "Flutter-разработчик"',
    ),
    _intent(
        "ml-ai-llm",
        "en",
        '"Machine Learning Engineer" OR "ML Engineer" OR "AI Engineer" OR "AI Developer" OR "LLM Engineer"',
    ),
    _intent(
        "ml-ai-llm",
        "ru",
        '"инженер машинного обучения" OR "ML-инженер" OR "AI-инженер" OR "AI-разработчик" OR "LLM-инженер"',
    ),
    _intent(
        "gamedev",
        "en",
        '"Game Developer" OR "Game Engineer" OR "Gameplay Developer" OR "Gameplay Programmer"',
    ),
    _intent(
        "gamedev",
        "ru",
        '"разработчик игр" OR "игровой разработчик" OR "геймплей-программист"',
    ),
    _intent(
        "automation-qa",
        "en",
        '"QA Automation Engineer" OR "Automation QA Engineer" OR "Test Automation Engineer"',
    ),
    _intent(
        "automation-qa",
        "ru",
        '"инженер по автоматизации тестирования" OR "QA automation инженер" OR "автоматизатор тестирования"',
    ),
    _intent(
        "devsecops",
        "en",
        '"DevSecOps Engineer" OR "DevSecOps Developer"',
    ),
    _intent(
        "devsecops",
        "ru",
        '"DevSecOps-инженер" OR "инженер DevSecOps"',
    ),
    _intent(
        "blockchain",
        "en",
        '"Blockchain Developer" OR "Blockchain Engineer" OR "Smart Contract Developer"',
    ),
    _intent(
        "blockchain",
        "ru",
        '"блокчейн-разработчик" OR "блокчейн-инженер" OR "разработчик смарт-контрактов"',
    ),
    _intent(
        "enterprise-developer",
        "en",
        '"Enterprise Developer" OR "Java Developer" OR "Python Developer" OR "Go Developer" OR "Node.js Developer" OR "Software Programmer"',
    ),
    _intent(
        "enterprise-developer",
        "ru",
        '"корпоративный разработчик" OR "Java-разработчик" OR "Python-разработчик" OR "Go-разработчик" OR "программист"',
    ),
    _intent(
        "software-architecture-lead",
        "en",
        '"Software Architect" OR "Technical Lead" OR "Tech Lead"',
    ),
    _intent(
        "software-architecture-lead",
        "ru",
        '"архитектор ПО" OR "программный архитектор" OR "технический лидер" OR "техлид"',
    ),
    _intent(
        "ui-ux",
        "en",
        '"UI/UX Designer" OR "UX/UI Designer" OR "UI Designer" OR "UX Designer"',
    ),
    _intent(
        "ui-ux",
        "ru",
        '"UI/UX-дизайнер" OR "UX/UI-дизайнер" OR "дизайнер интерфейсов" OR "UX-дизайнер"',
    ),
)


def select_search_intents(raw_query: str) -> tuple[SearchIntent, ...]:
    """Keep configured ``||`` queries, otherwise use the named default profile."""

    custom_queries = tuple(query.strip() for query in (raw_query or "").split("||") if query.strip())
    if not custom_queries:
        return DEFAULT_SEARCH_INTENTS
    return tuple(
        SearchIntent(family=f"custom-{index}", language="custom", query=query)
        for index, query in enumerate(custom_queries, start=1)
    )


def fair_query_limits(total_limit: int, intents: Sequence[SearchIntent]) -> tuple[int, ...]:
    """Split a non-negative total quota as evenly as possible in intent order."""

    if not intents:
        return ()
    quota = max(total_limit, 0)
    base, remainder = divmod(quota, len(intents))
    return tuple(base + (1 if index < remainder else 0) for index in range(len(intents)))


def select_cycle_intents(
    intents: Sequence[SearchIntent],
    *,
    max_intents: int,
    cycle_index: int,
) -> tuple[SearchIntent, ...]:
    """Rotate a bounded intent window so the whole profile is covered over time."""

    if not intents or max_intents <= 0:
        return ()
    count = min(max_intents, len(intents))
    start = (max(cycle_index, 0) * count) % len(intents)
    return tuple(intents[(start + offset) % len(intents)] for offset in range(count))
