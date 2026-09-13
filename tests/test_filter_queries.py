from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.sources.filter_queries import (
    RU_JOB_DOMAIN_HINTS,
    apply_filter_queries,
    build_apify_queries,
    build_guest_keywords,
    build_russia_search_intents,
    build_search_intents,
    build_site_query,
)
from tg_vacancy_bot.sources.linkedin_search_profile import (
    HIRING_INTENT,
    LINKEDIN_POST_SITE_SCOPE,
)


def _settings() -> Settings:
    return Settings(TELEGRAM_BOT_TOKEN="token", TARGET_CHAT_ID="@target")


def test_backend_middle_intent_content() -> None:
    intents = build_search_intents(("backend",), ("middle",))
    assert len(intents) == 2
    by_language = {intent.language: intent for intent in intents}
    assert "Middle Backend Developer" in by_language["en"].query
    assert "мидл" in by_language["ru"].query
    for intent in intents:
        assert LINKEDIN_POST_SITE_SCOPE in intent.query
    assert HIRING_INTENT["en"] in by_language["en"].query
    assert HIRING_INTENT["ru"] in by_language["ru"].query
    assert by_language["en"].family == "backend"


def test_site_query_joins_with_fallback_separator() -> None:
    intents = build_search_intents(("backend",), ("middle",))
    assert build_site_query(intents) == " || ".join(intent.query for intent in intents)


def test_apify_queries_have_length_limit() -> None:
    queries = build_apify_queries(("backend", "frontend"), ("junior", "middle", "senior"))
    assert queries
    assert all(len(query) <= 85 for query in queries)
    assert any(query.startswith("Hiring ") for query in queries)
    assert any(query.startswith("Ищем ") for query in queries)


def test_guest_keywords_plain_format() -> None:
    keywords = build_guest_keywords(("backend",), ("middle",))
    assert "middle backend developer" in keywords
    assert "мидл бэкенд-разработчик" in keywords
    assert all("||" not in keyword and '"' not in keyword for keyword in keywords)


def test_manual_query_is_not_overwritten() -> None:
    settings = _settings().model_copy(update={"linkedin_post_search_query": "custom query"})
    updated = apply_filter_queries(settings, ("backend",), ("middle",))
    assert updated.linkedin_post_search_query == "custom query"
    assert "Middle Backend Developer" in updated.linkedin_post_scraper_query
    # Original settings object is never mutated.
    assert settings.linkedin_post_scraper_query != updated.linkedin_post_scraper_query


def test_empty_filter_falls_back_to_junior_frontend_fullstack() -> None:
    intents = build_search_intents((), ())
    assert any("Junior Frontend" in intent.query for intent in intents)
    families = {intent.family for intent in intents}
    assert {"frontend", "fullstack"} <= families


def test_russia_search_intents_have_no_linkedin_site_scope() -> None:
    intents = build_russia_search_intents(("backend",), ("middle",))
    assert len(intents) == 2
    for intent in intents:
        assert "site:linkedin" not in intent.query
        assert LINKEDIN_POST_SITE_SCOPE not in intent.query


def test_russia_search_intents_builds_two_languages_per_specialty() -> None:
    intents = build_russia_search_intents(("frontend", "backend"), ("junior",))

    by_family: dict[str, set[str]] = {}
    for intent in intents:
        by_family.setdefault(intent.family, set()).add(intent.language)
    assert set(by_family) == {"frontend", "backend"}
    for languages in by_family.values():
        assert languages == {"en", "ru"}


def test_russia_search_intents_frontend_junior_ru_query_contains_both_terms() -> None:
    intents = build_russia_search_intents(("frontend",), ("junior",))
    ru = next(intent for intent in intents if intent.language == "ru")

    assert "джуниор" in ru.query.lower()
    assert "фронтенд" in ru.query.lower()
    assert HIRING_INTENT["ru"] in ru.query

    en = next(intent for intent in intents if intent.language == "en")
    assert "Junior Frontend" in en.query
    assert HIRING_INTENT["en"] in en.query


def test_russia_search_intents_families_are_correct() -> None:
    intents = build_russia_search_intents(("frontend",), ("junior",))

    assert {intent.family for intent in intents} == {"frontend"}
    assert {intent.language for intent in intents} == {"en", "ru"}
    assert all(intent.query for intent in intents)


def test_russia_search_intents_empty_filter_falls_back_to_junior_frontend_fullstack() -> None:
    intents = build_russia_search_intents((), ())
    assert any("Junior Frontend" in intent.query for intent in intents)
    assert any("Junior Fullstack" in intent.query for intent in intents)
    families = {intent.family for intent in intents}
    assert {"frontend", "fullstack"} <= families


def test_russia_job_domain_hints_are_exported() -> None:
    assert RU_JOB_DOMAIN_HINTS
    assert RU_JOB_DOMAIN_HINTS[0] == "hh.ru"
    assert "superjob.ru" in RU_JOB_DOMAIN_HINTS
