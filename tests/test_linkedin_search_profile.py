import re
from dataclasses import FrozenInstanceError

import pytest

from tg_vacancy_bot.sources.linkedin_search_profile import (
    DEFAULT_SEARCH_INTENTS,
    HIRING_INTENT,
    LINKEDIN_POST_SITE_SCOPE,
    SearchIntent,
    fair_query_limits,
    select_cycle_intents,
    select_search_intents,
)


EXPECTED_FAMILIES = {
    "backend-software",
    "frontend",
    "fullstack",
    "mobile",
    "ml-ai-llm",
    "gamedev",
    "automation-qa",
    "devsecops",
    "blockchain",
    "enterprise-developer",
    "software-architecture-lead",
    "ui-ux",
}


def test_default_profile_covers_named_families_in_russian_and_english() -> None:
    assert {intent.family for intent in DEFAULT_SEARCH_INTENTS} == EXPECTED_FAMILIES
    for family in EXPECTED_FAMILIES:
        assert {intent.language for intent in DEFAULT_SEARCH_INTENTS if intent.family == family} == {"en", "ru"}


def test_default_queries_have_site_hiring_and_explicit_role_constraints() -> None:
    explicit_role_terms = {
        "developer",
        "engineer",
        "programmer",
        "architect",
        "lead",
        "designer",
        "разработчик",
        "инженер",
        "программист",
        "архитектор",
        "техлид",
        "лидер",
        "дизайнер",
        "автоматизатор",
    }

    for intent in DEFAULT_SEARCH_INTENTS:
        assert LINKEDIN_POST_SITE_SCOPE in intent.query
        assert HIRING_INTENT[intent.language] in intent.query
        role_clause = intent.query.rsplit(" (", maxsplit=1)[-1].rstrip(")")
        role_phrases = re.findall(r'"([^"]+)"', role_clause)
        assert role_phrases
        assert all(
            any(role_term in role_phrase.lower() for role_term in explicit_role_terms)
            for role_phrase in role_phrases
        )


def test_search_intent_is_immutable() -> None:
    intent = DEFAULT_SEARCH_INTENTS[0]

    with pytest.raises(FrozenInstanceError):
        intent.family = "changed"  # type: ignore[misc]


def test_select_search_intents_uses_defaults_for_blank_input() -> None:
    assert select_search_intents("  ") is DEFAULT_SEARCH_INTENTS


def test_select_search_intents_preserves_custom_double_pipe_queries() -> None:
    first = '(site:linkedin.com/posts) ("we are hiring") ("Backend Developer")'
    second = '(site:linkedin.com/feed/update) ("ищем") ("фронтенд-разработчик")'

    assert select_search_intents(f" {first} ||  || {second} ") == (
        SearchIntent(family="custom-1", language="custom", query=first),
        SearchIntent(family="custom-2", language="custom", query=second),
    )


@pytest.mark.parametrize(
    ("total_limit", "intent_count", "expected"),
    [
        (0, 3, (0, 0, 0)),
        (-5, 3, (0, 0, 0)),
        (2, 4, (1, 1, 0, 0)),
        (10, 3, (4, 3, 3)),
        (12, 3, (4, 4, 4)),
    ],
)
def test_fair_query_limits_are_balanced_and_non_negative(
    total_limit: int,
    intent_count: int,
    expected: tuple[int, ...],
) -> None:
    intents = DEFAULT_SEARCH_INTENTS[:intent_count]

    limits = fair_query_limits(total_limit, intents)

    assert limits == expected
    assert all(limit >= 0 for limit in limits)
    assert max(limits, default=0) - min(limits, default=0) <= 1
    assert sum(limits) == max(total_limit, 0)


def test_fair_query_limits_returns_empty_for_no_intents() -> None:
    assert fair_query_limits(10, ()) == ()


def test_select_cycle_intents_rotates_through_full_profile() -> None:
    first = select_cycle_intents(DEFAULT_SEARCH_INTENTS, max_intents=6, cycle_index=0)
    second = select_cycle_intents(DEFAULT_SEARCH_INTENTS, max_intents=6, cycle_index=1)
    third = select_cycle_intents(DEFAULT_SEARCH_INTENTS, max_intents=6, cycle_index=2)
    fourth = select_cycle_intents(DEFAULT_SEARCH_INTENTS, max_intents=6, cycle_index=3)

    assert first + second + third + fourth == DEFAULT_SEARCH_INTENTS


def test_select_cycle_intents_handles_wraparound_and_bounds() -> None:
    intents = DEFAULT_SEARCH_INTENTS[:5]

    assert select_cycle_intents(intents, max_intents=3, cycle_index=1) == (
        intents[3],
        intents[4],
        intents[0],
    )
    assert select_cycle_intents(intents, max_intents=10, cycle_index=3) == intents
    assert select_cycle_intents(intents, max_intents=0, cycle_index=0) == ()
