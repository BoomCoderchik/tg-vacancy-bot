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
        "frontend",
        "en",
        '"Junior Frontend Developer" OR "Junior Front-End Developer" OR "Junior Frontend Engineer" '
        'OR "Entry Level Frontend Developer" OR "Intern Frontend Developer"',
    ),
    _intent(
        "frontend",
        "ru",
        '"джуниор фронтенд-разработчик" OR "junior frontend-разработчик" '
        'OR "фронтенд-разработчик без опыта" OR "стажер фронтенд-разработчик"',
    ),
    _intent(
        "fullstack",
        "en",
        '"Junior Fullstack Developer" OR "Junior Full-Stack Developer" OR "Junior Full Stack Engineer" '
        'OR "Entry Level Fullstack Developer" OR "Intern Fullstack Developer"',
    ),
    _intent(
        "fullstack",
        "ru",
        '"джуниор фулстек-разработчик" OR "junior fullstack-разработчик" '
        'OR "фулстек-разработчик без опыта" OR "стажер fullstack-разработчик"',
    ),
    _intent(
        "frontend",
        "en",
        '"Frontend Developer Intern" OR "Intern Frontend Developer" '
        'OR "Frontend Developer Internship" OR "Trainee Frontend Developer"',
    ),
    _intent(
        "frontend",
        "ru",
        '"стажировка фронтенд-разработчик" OR "фронтенд-разработчик стажировка" '
        'OR "интерн фронтенд-разработчик" OR "trainee фронтенд-разработчик"',
    ),
    _intent(
        "fullstack",
        "en",
        '"Fullstack Developer Intern" OR "Intern Fullstack Developer" '
        'OR "Full Stack Developer Internship" OR "Trainee Full Stack Developer"',
    ),
    _intent(
        "fullstack",
        "ru",
        '"стажировка фулстек-разработчик" OR "фулстек-разработчик стажировка" '
        'OR "интерн фулстек-разработчик" OR "trainee fullstack-разработчик"',
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
