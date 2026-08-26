import asyncio
from datetime import UTC, datetime

from tg_vacancy_bot import linkedin_diagnostics
from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.linkedin_diagnostics import (
    MAX_DIAGNOSTIC_RESULTS_PER_PROVIDER,
    LinkedInDiagnosticReport,
    LinkedInProviderDiagnosticResult,
    collect_linkedin_diagnostics,
    format_linkedin_diagnostics,
)
from tg_vacancy_bot.sources.adapters.linkedin_post_scraper import SearchHtmlResult
from tg_vacancy_bot.sources.adapters.linkedin_post_search import LinkedInPostCandidate
from tg_vacancy_bot.sources.adapters.linkedin_post_search import LinkedInSearchProviderError


POST_URL = "https://www.linkedin.com/posts/example_activity-7483822807449600000-example"


def _candidate(url: str = POST_URL) -> LinkedInPostCandidate:
    return LinkedInPostCandidate(
        url=url,
        search_title="Sensitive snippet title",
        snippet="Sensitive snippet body",
        date_text="",
        provider="test",
        query="test query",
    )


def test_diagnostics_probes_free_providers_without_any_key(monkeypatch) -> None:
    settings = Settings(
        SERPAPI_API_KEY="",
        LINKEDIN_HEADLESS_ACCESS_AUTHORIZED=False,
        LINKEDIN_HEADLESS_PERMISSION_REFERENCE="",
    )

    async def fake_free_results(session, provider: str, query: str):
        if provider == "duckduckgo":
            return [
                SearchHtmlResult(
                    title="Hiring Junior Frontend Developer",
                    link=POST_URL,
                    snippet="We are hiring.",
                    date_text="",
                )
            ]
        return []

    monkeypatch.setattr(linkedin_diagnostics, "_fetch_free_search_results", fake_free_results)

    report = asyncio.run(collect_linkedin_diagnostics(settings, limit=10))
    output = format_linkedin_diagnostics(report)

    assert report.status == "ok"
    assert report.permission_gate == "not_authorized"
    assert report.provider_count == len(settings.linkedin_post_scraper_search_providers)
    assert report.urls == (POST_URL,)
    assert "provider=duckduckgo" in output
    assert "provider=bing_rss" in output


def test_diagnostics_free_path_reports_provider_errors_safely(monkeypatch) -> None:
    settings = Settings(
        SERPAPI_API_KEY="",
        LINKEDIN_HEADLESS_ACCESS_AUTHORIZED=True,
        LINKEDIN_HEADLESS_PERMISSION_REFERENCE="approval-reference",
    )

    async def failing_free_results(session, provider: str, query: str):
        if provider == "duckduckgo":
            raise TimeoutError("sensitive endpoint details")
        return []

    monkeypatch.setattr(linkedin_diagnostics, "_fetch_free_search_results", failing_free_results)

    report = asyncio.run(collect_linkedin_diagnostics(settings, limit=10))
    output = format_linkedin_diagnostics(report)

    duckduckgo = next(provider for provider in report.providers if provider.provider == "duckduckgo")
    assert duckduckgo.status == "error"
    assert duckduckgo.error_type == "TimeoutError"
    assert report.status == "degraded"
    assert report.permission_gate == "authorized"
    assert "sensitive endpoint details" not in output


def test_diagnostics_continues_after_query_error_and_deduplicates(monkeypatch) -> None:
    calls = {"count": 0}

    class MixedProvider:
        def __init__(self, settings: Settings) -> None:
            self.settings = settings

        async def discover(self, *, limit: int):
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("message contains super-secret-key")
            return [_candidate(), _candidate()]

    monkeypatch.setattr(linkedin_diagnostics, "LinkedInPostSearchAdapter", MixedProvider)
    monkeypatch.setattr(
        linkedin_diagnostics,
        "utcnow",
        lambda: datetime(2026, 7, 19, 12, 0, tzinfo=UTC),
    )
    settings = Settings(
        SERPAPI_API_KEY="super-secret-key",
        LINKEDIN_POST_HEADLESS_QUERY="first query || second query",
        LINKEDIN_HEADLESS_ACCESS_AUTHORIZED=True,
        LINKEDIN_HEADLESS_PERMISSION_REFERENCE="approval-reference",
    )

    report = asyncio.run(collect_linkedin_diagnostics(settings, limit=10))
    output = format_linkedin_diagnostics(report)

    assert report.status == "degraded"
    assert report.permission_gate == "authorized"
    assert report.candidate_count == 1
    assert report.unique_count == 1
    assert report.urls == (POST_URL,)
    assert report.fresh_date_hints == 1
    assert report.stale_date_hints == 0
    assert report.undated == 0
    assert "provider=serpapi status=degraded queries=2 query_errors=1 candidates=1" in output
    assert "profile_intents=2/2" in output
    assert "date_hints=fresh:1,stale:0,undated:0" in output
    assert "super-secret-key" not in output
    assert "Sensitive snippet" not in output


def test_diagnostics_formats_bounded_public_urls() -> None:
    urls = tuple(f"https://www.linkedin.com/posts/example-{index}" for index in range(3))
    report = LinkedInDiagnosticReport(
        status="ok",
        permission_gate="incomplete",
        providers=(LinkedInProviderDiagnosticResult(provider="serpapi", urls=urls),),
        urls=urls,
    )

    output = format_linkedin_diagnostics(report, show_limit=1)

    assert "stage=discovery status=ok permission_gate=incomplete" in output
    assert "url=https://www.linkedin.com/posts/example-0" in output
    assert "example-1" not in output
    assert "urls_omitted=2" in output


def test_diagnostics_distinguishes_empty_and_all_provider_errors(monkeypatch) -> None:
    seen_limits: list[int] = []

    class EmptyProvider:
        def __init__(self, settings: Settings) -> None:
            self.settings = settings

        async def discover(self, *, limit: int):
            seen_limits.append(limit)
            return []

    class FailingProvider(EmptyProvider):
        async def discover(self, *, limit: int):
            seen_limits.append(limit)
            raise TimeoutError("sensitive provider details")

    settings = Settings(
        SERPAPI_API_KEY="secret",
        LINKEDIN_POST_HEADLESS_QUERY="custom query",
    )
    monkeypatch.setattr(linkedin_diagnostics, "LinkedInPostSearchAdapter", EmptyProvider)
    empty_report = asyncio.run(collect_linkedin_diagnostics(settings, limit=10000))

    monkeypatch.setattr(linkedin_diagnostics, "LinkedInPostSearchAdapter", FailingProvider)
    error_report = asyncio.run(collect_linkedin_diagnostics(settings, limit=10000))

    assert empty_report.status == "no_results"
    assert error_report.status == "provider_error"
    assert error_report.providers[0].error_type == "TimeoutError"
    assert seen_limits == [MAX_DIAGNOSTIC_RESULTS_PER_PROVIDER] * 2


def test_diagnostics_reports_safe_http_status_without_provider_details(monkeypatch) -> None:
    class FailingProvider:
        def __init__(self, settings: Settings) -> None:
            self.settings = settings

        async def discover(self, *, limit: int):
            raise LinkedInSearchProviderError(429)

    monkeypatch.setattr(linkedin_diagnostics, "LinkedInPostSearchAdapter", FailingProvider)
    settings = Settings(SERPAPI_API_KEY="secret", LINKEDIN_POST_HEADLESS_QUERY="custom query")

    report = asyncio.run(collect_linkedin_diagnostics(settings, limit=1))

    assert report.providers[0].error_type == "Http429"


def test_diagnostics_reports_safe_network_error_type(monkeypatch) -> None:
    class FailingProvider:
        def __init__(self, settings: Settings) -> None:
            self.settings = settings

        async def discover(self, *, limit: int):
            raise LinkedInSearchProviderError(failure_type="ClientConnectorError")

    monkeypatch.setattr(linkedin_diagnostics, "LinkedInPostSearchAdapter", FailingProvider)
    settings = Settings(SERPAPI_API_KEY="secret", LINKEDIN_POST_HEADLESS_QUERY="custom query")

    report = asyncio.run(collect_linkedin_diagnostics(settings, limit=1))

    assert report.providers[0].error_type == "ClientConnectorError"


def test_diagnostics_counts_fresh_stale_and_undated_candidates(monkeypatch) -> None:
    fresh_url = POST_URL
    stale_url = "https://www.linkedin.com/posts/old_activity-7435364783379341312-example"
    undated_url = "https://www.linkedin.com/posts/no-date-example"

    class MixedProvider:
        def __init__(self, settings: Settings) -> None:
            self.settings = settings

        async def discover(self, *, limit: int):
            return [_candidate(fresh_url), _candidate(stale_url), _candidate(undated_url)]

    monkeypatch.setattr(linkedin_diagnostics, "LinkedInPostSearchAdapter", MixedProvider)
    monkeypatch.setattr(
        linkedin_diagnostics,
        "utcnow",
        lambda: datetime(2026, 7, 19, 12, 0, tzinfo=UTC),
    )
    settings = Settings(
        SERPAPI_API_KEY="secret",
        LINKEDIN_POST_HEADLESS_QUERY="custom query",
        LINKEDIN_POST_MAX_AGE_HOURS=240,
    )

    report = asyncio.run(collect_linkedin_diagnostics(settings, limit=10))

    assert report.fresh_date_hints == 1
    assert report.stale_date_hints == 1
    assert report.undated == 1
