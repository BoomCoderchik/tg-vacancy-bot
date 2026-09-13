import asyncio
from datetime import UTC, datetime

import pytest

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.sources.adapters import russia_vacancy_search
from tg_vacancy_bot.sources.adapters.russia_vacancy_search import (
    RussiaVacancySearchAdapter,
    _clean_search_title,
    _is_acceptable_url,
    _location_from_text,
    _result_to_vacancy,
    _stack_from_text,
)
from tg_vacancy_bot.sources.filter_queries import apply_filter_queries
from tg_vacancy_bot.sources.freshness import filter_fresh_vacancies
from tg_vacancy_bot.sources.search_providers import SearchHtmlResult

FIXED_NOW = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)


def _settings(**overrides) -> Settings:
    base = dict(
        RUSSIA_SEARCH_QUERY='"ищем" "джуниор фронтенд-разработчик"',
        RUSSIA_SEARCH_PROVIDERS="bing_rss,duckduckgo",
        RUSSIA_SEARCH_RESULTS_WANTED=10,
        SOURCE_MAX_AGE_HOURS=48,
    )
    base.update(overrides)
    return Settings(**base)


def _freeze_now(monkeypatch) -> None:
    monkeypatch.setattr(russia_vacancy_search, "utcnow", lambda: FIXED_NOW)


def test_russia_search_maps_bing_rss_result_with_parsed_date(monkeypatch) -> None:
    _freeze_now(monkeypatch)
    rss = """
    <rss version="2.0"><channel><item>
      <title>Junior Frontend Developer | hh.ru</title>
      <link>https://hh.ru/vacancy/123456</link>
      <description>&lt;p&gt;Ищем джуниор фронтенд-разработчика в Москве.&lt;/p&gt;</description>
      <pubDate>Sat, 18 Jul 2026 10:00:00 GMT</pubDate>
    </item></channel></rss>
    """

    async def fake_rss(session, query):
        return rss

    monkeypatch.setattr(russia_vacancy_search, "_fetch_bing_rss", fake_rss)

    vacancies = asyncio.run(
        RussiaVacancySearchAdapter(_settings(RUSSIA_SEARCH_PROVIDERS="bing_rss")).fetch()
    )

    assert len(vacancies) == 1
    vacancy = vacancies[0]
    assert vacancy.title == "Junior Frontend Developer"
    assert vacancy.url == "https://hh.ru/vacancy/123456"
    assert vacancy.description == "Ищем джуниор фронтенд-разработчика в Москве."
    assert vacancy.published_at == datetime(2026, 7, 18, 10, 0, tzinfo=UTC)
    assert vacancy.location == "Москва"
    assert "frontend" in vacancy.stack


def test_russia_search_parses_relative_dates_and_drops_stale(monkeypatch) -> None:
    _freeze_now(monkeypatch)
    html = (
        "<div class='result'>"
        "<a class='result__a' href='https://career.habr.com/vacancies/a'>Junior Frontend (2 days) | hh.ru</a>"
        "<div class='result__date'>2 days ago</div>"
        "<div class='result__snippet'>Ищем джуниор фронтенд-разработчика.</div>"
        "</div>"
        "<div class='result'>"
        "<a class='result__a' href='https://career.habr.com/vacancies/b'>Frontend Developer (вчера)</a>"
        "<div class='result__date'>вчера</div>"
        "<div class='result__snippet'>Ищем фронтенд-разработчика удалённо.</div>"
        "</div>"
        "<div class='result'>"
        "<a class='result__a' href='https://career.habr.com/vacancies/c'>Old Frontend Role</a>"
        "<div class='result__date'>5 days ago</div>"
        "<div class='result__snippet'>Ищем фронтенд-разработчика.</div>"
        "</div>"
    )

    async def fake_html(session, provider, query):
        return html

    monkeypatch.setattr(russia_vacancy_search, "_fetch_search_html", fake_html)

    vacancies = asyncio.run(
        RussiaVacancySearchAdapter(_settings(RUSSIA_SEARCH_PROVIDERS="duckduckgo")).fetch()
    )

    by_url = {vacancy.url: vacancy for vacancy in vacancies}
    assert set(by_url) == {
        "https://career.habr.com/vacancies/a",
        "https://career.habr.com/vacancies/b",
    }
    assert by_url["https://career.habr.com/vacancies/a"].published_at == datetime(
        2026, 7, 17, 12, 0, tzinfo=UTC
    )
    assert by_url["https://career.habr.com/vacancies/b"].published_at == datetime(
        2026, 7, 18, 12, 0, tzinfo=UTC
    )


def test_russia_search_publishes_undated_results(monkeypatch) -> None:
    _freeze_now(monkeypatch)
    html = (
        "<div class='result'>"
        "<a class='result__a' href='https://example.com/jobs/junior-frontend'>Junior Frontend Developer</a>"
        "<div class='result__snippet'>We are hiring a junior frontend developer.</div>"
        "</div>"
    )

    async def fake_html(session, provider, query):
        return html

    monkeypatch.setattr(russia_vacancy_search, "_fetch_search_html", fake_html)

    vacancies = asyncio.run(
        RussiaVacancySearchAdapter(_settings(RUSSIA_SEARCH_PROVIDERS="duckduckgo")).fetch()
    )

    assert len(vacancies) == 1
    assert vacancies[0].published_at is None
    assert filter_fresh_vacancies(
        vacancies,
        max_age_hours=48,
        current_time=FIXED_NOW,
        require_published_at=False,
    ) == vacancies


def test_russia_search_skips_challenged_provider_and_keeps_others(monkeypatch) -> None:
    _freeze_now(monkeypatch)
    html = (
        "<li class='b_algo'><h2><a href='https://career.habr.com/vacancies/junior'>Junior Frontend Developer</a></h2>"
        "<p>Ищем джуниор фронтенд-разработчика в Казани.</p></li>"
    )

    async def mixed_html(session, provider, query):
        if provider == "duckduckgo":
            return "<html>Sorry, your network appears to be sending automated queries.</html>"
        return html

    monkeypatch.setattr(russia_vacancy_search, "_fetch_search_html", mixed_html)

    vacancies = asyncio.run(
        RussiaVacancySearchAdapter(_settings(RUSSIA_SEARCH_PROVIDERS="duckduckgo,bing")).fetch()
    )

    assert len(vacancies) == 1
    assert vacancies[0].url == "https://career.habr.com/vacancies/junior"
    assert vacancies[0].location == "Казань"


def test_russia_search_continues_after_provider_failure(monkeypatch) -> None:
    _freeze_now(monkeypatch)
    html = (
        "<div class='result'>"
        "<a class='result__a' href='https://example.com/jobs/frontend'>Junior Frontend Developer</a>"
        "<div class='result__snippet'>We are hiring a junior frontend developer.</div>"
        "</div>"
    )

    async def failing_rss(session, query):
        raise RuntimeError("bing rss unavailable")

    async def working_html(session, provider, query):
        return html

    monkeypatch.setattr(russia_vacancy_search, "_fetch_bing_rss", failing_rss)
    monkeypatch.setattr(russia_vacancy_search, "_fetch_search_html", working_html)

    vacancies = asyncio.run(RussiaVacancySearchAdapter(_settings()).fetch())

    assert len(vacancies) == 1
    assert vacancies[0].url == "https://example.com/jobs/frontend"


def test_russia_search_raises_when_every_provider_fails(monkeypatch) -> None:
    async def failing_rss(session, query):
        raise RuntimeError("bing rss unavailable")

    async def failing_html(session, provider, query):
        raise RuntimeError(f"{provider} unavailable")

    monkeypatch.setattr(russia_vacancy_search, "_fetch_bing_rss", failing_rss)
    monkeypatch.setattr(russia_vacancy_search, "_fetch_search_html", failing_html)

    with pytest.raises(RuntimeError) as exc_info:
        asyncio.run(RussiaVacancySearchAdapter(_settings()).fetch())

    assert "no usable results" in str(exc_info.value)


def test_russia_search_dedups_normalized_urls_across_providers(monkeypatch) -> None:
    _freeze_now(monkeypatch)
    html = (
        "<div class='result'>"
        "<a class='result__a' href='https://hh.ru/vacancy/42'>Junior Frontend Developer | hh.ru</a>"
        "<div class='result__snippet'>Ищем джуниор фронтенд-разработчика.</div>"
        "</div>"
    )

    async def fake_html(session, provider, query):
        return html

    async def fake_rss(session, query):
        return (
            "<rss><channel><item><title>Same job</title><link>https://hh.ru/vacancy/42</link>"
            "<description>Ищем джуниор фронтенд-разработчика.</description>"
            "<pubDate></pubDate></item></channel></rss>"
        )

    monkeypatch.setattr(russia_vacancy_search, "_fetch_search_html", fake_html)
    monkeypatch.setattr(russia_vacancy_search, "_fetch_bing_rss", fake_rss)

    vacancies = asyncio.run(RussiaVacancySearchAdapter(_settings()).fetch())

    assert len(vacancies) == 1
    assert vacancies[0].url == "https://hh.ru/vacancy/42"


def test_russia_search_skips_spam_titles(monkeypatch) -> None:
    _freeze_now(monkeypatch)
    html = (
        "<div class='result'>"
        "<a class='result__a' href='https://example.com/spam'>Купить квартиру в Москве</a>"
        "<div class='result__snippet'>Срочная продажа от собственника.</div>"
        "</div>"
        "<div class='result'>"
        "<a class='result__a' href='https://example.com/job'>Junior Frontend Developer</a>"
        "<div class='result__snippet'>Ищем джуниор фронтенд-разработчика.</div>"
        "</div>"
    )

    async def fake_html(session, provider, query):
        return html

    monkeypatch.setattr(russia_vacancy_search, "_fetch_search_html", fake_html)

    vacancies = asyncio.run(
        RussiaVacancySearchAdapter(_settings(RUSSIA_SEARCH_PROVIDERS="duckduckgo")).fetch()
    )

    assert len(vacancies) == 1
    assert vacancies[0].url == "https://example.com/job"


def test_russia_search_excludes_search_engines_and_linkedin_urls() -> None:
    assert not _is_acceptable_url("https://www.bing.com/ck/a?!&u=a1foo")
    assert not _is_acceptable_url("https://duckduckgo.com/?q=junior")
    assert not _is_acceptable_url("https://www.mojeek.com/search?q=junior")
    assert not _is_acceptable_url("https://www.linkedin.com/jobs/view/123")
    assert not _is_acceptable_url("https://ru.linkedin.com/jobs")
    assert not _is_acceptable_url("not a url")
    assert not _is_acceptable_url("mailto:someone@example.com")
    assert _is_acceptable_url("https://example.com/jobs/1")
    assert _is_acceptable_url("http://hh.ru/vacancy/1")

    result = SearchHtmlResult(
        title="Hello | hh.ru",
        link="https://www.bing.com/ck/a?!&u=a1c2",
        snippet="Some snippet",
    )
    assert _result_to_vacancy(result) is None
    assert _result_to_vacancy(result) is None  # no exception path, twice safe


def test_clean_search_title_removes_site_suffixes_and_prefixes() -> None:
    assert _clean_search_title("Junior Frontend Developer | hh.ru") == "Junior Frontend Developer"
    assert _clean_search_title("Senior Go Developer - SuperJob") == "Senior Go Developer"
    assert _clean_search_title("Frontend Engineer — Хабр Карьера") == "Frontend Engineer"
    assert _clean_search_title("Data Engineer | SuperJob") == "Data Engineer"
    assert _clean_search_title("hh.ru | Junior Frontend Developer") == "Junior Frontend Developer"


def test_stack_and_location_heuristics() -> None:
    assert "frontend" in _stack_from_text("Разработчик React фронтенд TypeScript Python")
    assert "backend" in _stack_from_text("бэкенд разработчик на Java")
    assert "fullstack" in _stack_from_text("Full-Stack Developer")
    assert "python" in _stack_from_text("разработчик на питоне и Django")
    assert _location_from_text("Работа в Москве") == "Москва"
    assert _location_from_text("Работа в Казани") == "Казань"
    assert _location_from_text("Удалённая работа") == "Удалённо"
    assert _location_from_text("We offer remote work") == "Удалённо"
    assert _location_from_text("No location here") is None


def test_apply_filter_queries_fills_russia_query_from_filter() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        RUSSIA_SEARCH_QUERY="",
    )
    updated = apply_filter_queries(settings, ("frontend",), ("junior",))

    assert updated.russia_search_query
    lower = updated.russia_search_query.lower()
    assert "фронтенд" in lower
    assert "джуниор" in lower
    assert "site:linkedin" not in lower


def test_apply_filter_queries_never_overwrites_manual_russia_query() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        RUSSIA_SEARCH_QUERY="manual query",
    )
    updated = apply_filter_queries(settings, ("frontend",), ("junior",))

    assert updated.russia_search_query == "manual query"


def test_apply_filter_queries_does_not_mutate_original_settings() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        RUSSIA_SEARCH_QUERY="",
    )
    apply_filter_queries(settings, ("frontend",), ("junior",))

    assert settings.russia_search_query == ""