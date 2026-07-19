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


def test_diagnostics_reports_missing_key_without_browser_or_publishing() -> None:
    settings = Settings(
        SERPAPI_API_KEY="",
        SERPER_API_KEY="",
        LINKEDIN_HEADLESS_ACCESS_AUTHORIZED=False,
        LINKEDIN_HEADLESS_PERMISSION_REFERENCE="",
    )

    report = asyncio.run(collect_linkedin_diagnostics(settings, limit=10))

    assert report.status == "misconfigured"
    assert report.permission_gate == "not_authorized"
    assert report.providers == ()
    assert report.urls == ()


def test_diagnostics_continues_after_provider_error_and_deduplicates(monkeypatch) -> None:
    class FailingProvider:
        def __init__(self, settings: Settings) -> None:
            self.settings = settings

        async def discover(self, *, limit: int):
            raise RuntimeError("message contains super-secret-key")

    class WorkingProvider:
        def __init__(self, settings: Settings) -> None:
            self.settings = settings

        async def discover(self, *, limit: int):
            return [_candidate(), _candidate()]

    monkeypatch.setattr(linkedin_diagnostics, "LinkedInPostSearchAdapter", FailingProvider)
    monkeypatch.setattr(linkedin_diagnostics, "LinkedInPostSerperAdapter", WorkingProvider)
    monkeypatch.setattr(
        linkedin_diagnostics,
        "utcnow",
        lambda: datetime(2026, 7, 19, 12, 0, tzinfo=UTC),
    )
    settings = Settings(
        SERPAPI_API_KEY="super-secret-key",
        SERPER_API_KEY="second-secret-key",
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
    assert "provider=serpapi status=error queries=2 query_errors=2 candidates=0 error_type=RuntimeError" in output
    assert "provider=serper status=ok queries=2 query_errors=0 candidates=1" in output
    assert "profile_intents=2/2" in output
    assert "date_hints=fresh:1,stale:0,undated:0" in output
    assert "super-secret-key" not in output
    assert "second-secret-key" not in output
    assert "Sensitive snippet" not in output


def test_diagnostics_formats_bounded_public_urls() -> None:
    urls = tuple(f"https://www.linkedin.com/posts/example-{index}" for index in range(3))
    report = LinkedInDiagnosticReport(
        status="ok",
        permission_gate="incomplete",
        providers=(LinkedInProviderDiagnosticResult(provider="serper", urls=urls),),
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
        SERPER_API_KEY="",
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
        SERPER_API_KEY="",
        LINKEDIN_POST_HEADLESS_QUERY="custom query",
        LINKEDIN_POST_MAX_AGE_HOURS=120,
    )

    report = asyncio.run(collect_linkedin_diagnostics(settings, limit=10))

    assert report.fresh_date_hints == 1
    assert report.stale_date_hints == 1
    assert report.undated == 1
