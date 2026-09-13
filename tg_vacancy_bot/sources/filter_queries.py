"""Build LinkedIn discovery queries from the active vacancy filter.

Pure helpers without Telegram/store dependencies. Manual ``LINKEDIN_*``
queries set via ``.env`` take priority and are never overwritten: fields
whose current value differs from the ``Settings`` default are left alone.
"""

from __future__ import annotations

from collections.abc import Iterable

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.sources.filters import normalize_grades, normalize_specialties
from tg_vacancy_bot.sources.linkedin_search_profile import (
    HIRING_INTENT,
    LINKEDIN_POST_SITE_SCOPE,
    SearchIntent,
)

ROLE_CORES: dict[str, dict[str, list[str]]] = {
    "frontend": {
        "en": ["Frontend Developer", "Frontend Engineer"],
        "ru": ["фронтенд-разработчик", "frontend-разработчик"],
    },
    "backend": {
        "en": ["Backend Developer"],
        "ru": ["бэкенд-разработчик", "бекенд разработчик"],
    },
    "fullstack": {
        "en": ["Fullstack Developer", "Full Stack Engineer"],
        "ru": ["фулстек-разработчик", "fullstack-разработчик"],
    },
    "mobile": {
        "en": ["Mobile Developer"],
        "ru": ["мобильный разработчик"],
    },
    "qa": {
        "en": ["QA Engineer"],
        "ru": ["тестировщик", "QA-инженер"],
    },
    "devops": {
        "en": ["DevOps Engineer"],
        "ru": ["девопс-инженер"],
    },
    "data": {
        "en": ["Data Engineer"],
        "ru": ["дата-инженер", "аналитик данных"],
    },
    "design": {
        "en": ["Product Designer"],
        "ru": ["дизайнер", "продуктовый дизайнер"],
    },
}

GRADE_WORDS: dict[str, dict[str, list[str]]] = {
    "intern": {"en": ["Intern", "Trainee"], "ru": ["стажер"]},
    "junior": {"en": ["Junior"], "ru": ["джуниор"]},
    "middle": {"en": ["Middle"], "ru": ["мидл", "миддл"]},
    "senior": {"en": ["Senior"], "ru": ["сеньор"]},
    "lead": {"en": ["Lead"], "ru": ["тимлид"]},
}

_LANGUAGES: tuple[str, str] = ("en", "ru")
_MAX_QUOTED_PER_INTENT = 6
_APIFY_MAX_LENGTH = 85

# Domain priority hints for the future open web (non-LinkedIn) adapter. Not a
# strict filter: only an ordering preference when reading search results.
RU_JOB_DOMAIN_HINTS: tuple[str, ...] = (
    "hh.ru",
    "career.habr.com",
    "career.habr.com/company",
    "superjob.ru",
    "getmatch.ru",
    "vc.ru",
    "teletype.in",
    "remoters",
    "remotejob",
)


def _expand_specialties(specialties: Iterable[str]) -> list[str]:
    """Expand the combined ``frontend_fullstack`` into its two families."""

    expanded: list[str] = []
    for specialty in specialties:
        if specialty == "frontend_fullstack":
            expanded.extend(["frontend", "fullstack"])
        else:
            expanded.append(specialty)
    return list(dict.fromkeys(expanded))


def _active_specialties(specialties: str | Iterable[str] | None) -> list[str]:
    return _expand_specialties(normalize_specialties(specialties))


def _active_grades(grades: str | Iterable[str] | None) -> list[str]:
    return normalize_grades(grades)


def _quoted_combos(specialty: str, language: str, active_grades: list[str]) -> str:
    """Build the ``"grade role" OR "grade role"`` snippet for one language."""

    cores = ROLE_CORES.get(specialty, {}).get(language, [])
    combos: list[str] = []
    for grade in active_grades:
        for grade_word in GRADE_WORDS.get(grade, {}).get(language, []):
            for core in cores:
                combos.append(f"{grade_word} {core}")
    return " OR ".join(f'"{combo}"' for combo in combos[:_MAX_QUOTED_PER_INTENT])


def build_search_intents(
    specialties: str | Iterable[str] | None,
    grades: str | Iterable[str] | None,
) -> tuple[SearchIntent, ...]:
    """Build one search intent per (specialty x language)."""

    active_specialties = _active_specialties(specialties)
    active_grades = _active_grades(grades)
    intents: list[SearchIntent] = []
    for specialty in active_specialties:
        if not ROLE_CORES.get(specialty):
            continue
        for language in _LANGUAGES:
            quoted = _quoted_combos(specialty, language, active_grades)
            if not quoted:
                continue
            query = f"{LINKEDIN_POST_SITE_SCOPE} {HIRING_INTENT[language]} ({quoted})"
            intents.append(SearchIntent(family=specialty, language=language, query=query))
    return tuple(intents)


def build_russia_search_intents(
    specialties: str | Iterable[str] | None,
    grades: str | Iterable[str] | None,
) -> tuple[SearchIntent, ...]:
    """Build open-web (non-LinkedIn) search intents for Russian job sources.

    Same (specialty x language) shape as ``build_search_intents`` but without
    the ``site:linkedin.com`` scope: the queries target general web search
    results that may point to hh.ru, SuperJob, Habr Career, and similar sites.
    """

    active_specialties = _active_specialties(specialties)
    active_grades = _active_grades(grades)
    intents: list[SearchIntent] = []
    for specialty in active_specialties:
        if not ROLE_CORES.get(specialty):
            continue
        for language in _LANGUAGES:
            quoted = _quoted_combos(specialty, language, active_grades)
            if not quoted:
                continue
            query = f"{HIRING_INTENT[language]} ({quoted})"
            intents.append(SearchIntent(family=specialty, language=language, query=query))
    return tuple(intents)


def build_site_query(intents: Iterable[SearchIntent]) -> str:
    """Join intent queries with the ``||`` fallback separator."""

    return " || ".join(intent.query for intent in intents)


def build_apify_queries(
    specialties: str | Iterable[str] | None,
    grades: str | Iterable[str] | None,
    limit: int = 12,
) -> list[str]:
    """Build plain-text Apify queries, each strictly ``<=85`` chars."""

    active_specialties = _active_specialties(specialties)
    active_grades = _active_grades(grades)
    queries: list[str] = []
    for language, template in (("en", "Hiring {}"), ("ru", "Ищем {}")):
        for specialty in active_specialties:
            cores = ROLE_CORES.get(specialty, {}).get(language, [])
            for grade in active_grades:
                for grade_word in GRADE_WORDS.get(grade, {}).get(language, []):
                    for core in cores:
                        candidate = template.format(f"{grade_word} {core}")
                        if len(candidate) <= _APIFY_MAX_LENGTH and candidate not in queries:
                            queries.append(candidate)
    return queries[: max(limit, 0)]


def build_guest_keywords(
    specialties: str | Iterable[str] | None,
    grades: str | Iterable[str] | None,
    limit: int = 12,
) -> list[str]:
    """Build plain guest-job keywords (no boolean operators)."""

    active_specialties = _active_specialties(specialties)
    active_grades = _active_grades(grades)
    keywords: list[str] = []
    for language in _LANGUAGES:
        for specialty in active_specialties:
            cores = ROLE_CORES.get(specialty, {}).get(language, [])
            for grade in active_grades:
                for grade_word in GRADE_WORDS.get(grade, {}).get(language, []):
                    for core in cores:
                        candidate = f"{grade_word} {core}".lower()
                        if candidate not in keywords:
                            keywords.append(candidate)
    return keywords[: max(limit, 0)]


def apply_filter_queries(
    settings: Settings,
    specialties: str | Iterable[str] | None,
    grades: str | Iterable[str] | None,
) -> Settings:
    """Return a copy of ``settings`` with filter-generated discovery queries.

    Only fields still holding their ``Settings`` default are replaced; a
    manually configured ``LINKEDIN_*`` query always wins. The headless raw
    query is replaced only when it is empty (empty means autogeneration).
    The original ``settings`` object is never mutated.
    """

    active_specialties = _active_specialties(specialties)
    active_grades = _active_grades(grades)
    intents = build_search_intents(active_specialties, active_grades)
    site_query = build_site_query(intents)
    fields = Settings.model_fields
    updates: dict[str, str] = {}
    if settings.linkedin_post_search_query == fields["linkedin_post_search_query"].default:
        updates["linkedin_post_search_query"] = site_query
    if settings.linkedin_post_scraper_query == fields["linkedin_post_scraper_query"].default:
        updates["linkedin_post_scraper_query"] = site_query
    if (
        settings.linkedin_post_apify_search_queries_raw
        == fields["linkedin_post_apify_search_queries_raw"].default
    ):
        updates["linkedin_post_apify_search_queries_raw"] = "||".join(
            build_apify_queries(active_specialties, active_grades)
        )
    if (
        settings.linkedin_jobs_guest_keywords_raw
        == fields["linkedin_jobs_guest_keywords_raw"].default
    ):
        updates["linkedin_jobs_guest_keywords_raw"] = "||".join(
            build_guest_keywords(active_specialties, active_grades)
        )
    if not (settings.linkedin_post_headless_query or "").strip():
        updates["linkedin_post_headless_query"] = site_query
    if not settings.russia_search_query.strip():
        updates["russia_search_query"] = build_site_query(
            build_russia_search_intents(active_specialties, active_grades)
        )
    if not updates:
        return settings
    return settings.model_copy(update=updates)
