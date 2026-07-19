import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from contextlib import asynccontextmanager

import aiohttp
import pytest

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.sources.adapters import linkedin_post_headless
from tg_vacancy_bot.sources.adapters.linkedin_post_headless import LinkedInPostHeadlessAdapter
from tg_vacancy_bot.sources.adapters.linkedin_post_search import (
    LinkedInPostCandidate,
    _canonicalize_linkedin_post_url,
    _get_search_payload,
    _google_recency_filter,
    _result_to_candidate,
    LinkedInSearchProviderError,
    LinkedInPostSearchAdapter,
    LinkedInPostSerperAdapter,
)
from tg_vacancy_bot.sources.linkedin_search_profile import (
    DEFAULT_SEARCH_INTENTS,
    select_cycle_intents,
)


POST_URL = "https://www.linkedin.com/posts/example_activity-7483822807449600000-example"


def _candidate(url: str = POST_URL) -> LinkedInPostCandidate:
    return LinkedInPostCandidate(
        url=url,
        search_title="",
        snippet="",
        date_text="",
        provider="Test discovery",
        query="site:linkedin.com/posts developer",
    )


def test_canonicalize_linkedin_post_url_strips_tracking_query_and_fragment() -> None:
    url = (
        "http://uk.linkedin.com/posts/example_activity-7483822807449600000-example/"
        "?utm_source=search&trackingId=secret#comments"
    )

    assert _canonicalize_linkedin_post_url(url) == POST_URL


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/?next=https://www.linkedin.com/posts/example",
        "https://linkedin.com.evil.example/posts/example",
        "https://www.linkedin.com/jobs/view/123",
        "https://www.linkedin.com/foo/linkedin.com/posts/example",
        "https://www.linkedin.com/posts/",
    ],
)
def test_canonicalize_linkedin_post_url_rejects_off_domain_or_non_post_urls(url: str) -> None:
    assert _canonicalize_linkedin_post_url(url) == ""


def test_result_to_candidate_accepts_url_without_search_metadata() -> None:
    candidate = _result_to_candidate(
        {"link": f"{POST_URL}?trackingId=secret#comments"},
        provider="Serper",
        query="site:linkedin.com/posts developer",
    )

    assert candidate == LinkedInPostCandidate(
        url=POST_URL,
        search_title="",
        snippet="",
        date_text="",
        provider="Serper",
        query="site:linkedin.com/posts developer",
    )


@pytest.mark.parametrize(
    ("max_age_hours", "expected"),
    [
        (1, "qdr:h"),
        (24, "qdr:d"),
        (25, "qdr:w"),
        (120, "qdr:w"),
    ],
)
def test_google_recency_filter_uses_the_narrowest_supported_window(
    max_age_hours: int,
    expected: str,
) -> None:
    assert _google_recency_filter(max_age_hours) == expected


def test_serpapi_discovery_requests_a_server_side_recency_window(monkeypatch) -> None:
    captured_params: list[dict[str, object]] = []

    @asynccontextmanager
    async def fake_source_session(*args: object, **kwargs: object):
        yield object()

    async def fake_get_search_payload(session: object, url: str, *, params: dict[str, object]):
        captured_params.append(params)
        return {"organic_results": []}

    monkeypatch.setattr(
        "tg_vacancy_bot.sources.adapters.linkedin_post_search.source_session",
        fake_source_session,
    )
    monkeypatch.setattr(
        "tg_vacancy_bot.sources.adapters.linkedin_post_search._get_search_payload",
        fake_get_search_payload,
    )
    settings = Settings(
        SERPAPI_API_KEY="test-key",
        LINKEDIN_POST_SEARCH_QUERY="custom query",
        LINKEDIN_POST_MAX_AGE_HOURS=120,
    )

    assert asyncio.run(LinkedInPostSearchAdapter(settings).discover(limit=2)) == []
    assert captured_params == [
        {
            "engine": "google",
            "api_key": "test-key",
            "q": "custom query",
            "num": 2,
            "hl": "ru",
            "tbs": "qdr:w",
        }
    ]


def test_serper_discovery_requests_a_server_side_recency_window(monkeypatch) -> None:
    captured_payloads: list[dict[str, object]] = []

    @asynccontextmanager
    async def fake_source_session(*args: object, **kwargs: object):
        yield object()

    async def fake_post_search_payload(session: object, url: str, *, payload: dict[str, object]):
        captured_payloads.append(payload)
        return {"organic": []}

    monkeypatch.setattr(
        "tg_vacancy_bot.sources.adapters.linkedin_post_search.source_session",
        fake_source_session,
    )
    monkeypatch.setattr(
        "tg_vacancy_bot.sources.adapters.linkedin_post_search._post_search_payload",
        fake_post_search_payload,
    )
    settings = Settings(
        SERPER_API_KEY="test-key",
        LINKEDIN_POST_SEARCH_QUERY="custom query",
        LINKEDIN_POST_MAX_AGE_HOURS=120,
    )

    assert asyncio.run(LinkedInPostSerperAdapter(settings).discover(limit=2)) == []
    assert captured_payloads == [
        {"q": "custom query", "num": 2, "hl": "ru", "tbs": "qdr:w"}
    ]


def test_headless_keyed_discovery_preserves_candidate_without_date_or_snippet(monkeypatch) -> None:
    calls: list[tuple[int | None, str]] = []
    current_time = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)

    class FakeSearchProvider:
        def __init__(self, settings: Settings) -> None:
            self.settings = settings

        async def discover(self, *, limit: int | None = None) -> list[LinkedInPostCandidate]:
            calls.append((limit, self.settings.linkedin_post_search_query))
            return [_candidate()]

    monkeypatch.setattr(linkedin_post_headless, "LinkedInPostSearchAdapter", FakeSearchProvider)
    monkeypatch.setattr(linkedin_post_headless, "utcnow", lambda: current_time)
    settings = Settings(
        ENABLE_ARBEITNOW=False,
        ENABLE_WORKING_NOMADS=False,
        SERPAPI_API_KEY="test-key",
        SERPER_API_KEY="",
    )

    urls = asyncio.run(LinkedInPostHeadlessAdapter(settings)._discover_keyed_post_urls(limit=5))

    expected_intents = select_cycle_intents(
        DEFAULT_SEARCH_INTENTS,
        max_intents=6,
        cycle_index=linkedin_post_headless._search_cycle_index(current_time),
    )
    assert urls == (POST_URL,)
    assert calls == [(1, intent.query) for intent in expected_intents]


def test_headless_keyed_discovery_deduplicates_urls_across_providers(monkeypatch) -> None:
    class FakeProvider:
        def __init__(self, settings: Settings) -> None:
            self.settings = settings

        async def discover(self, *, limit: int | None = None) -> list[LinkedInPostCandidate]:
            return [_candidate(), _candidate()]

    monkeypatch.setattr(linkedin_post_headless, "LinkedInPostSearchAdapter", FakeProvider)
    monkeypatch.setattr(linkedin_post_headless, "LinkedInPostSerperAdapter", FakeProvider)
    settings = Settings(
        ENABLE_ARBEITNOW=False,
        ENABLE_WORKING_NOMADS=False,
        SERPAPI_API_KEY="serpapi-key",
        SERPER_API_KEY="serper-key",
        LINKEDIN_POST_HEADLESS_QUERY="custom query",
    )

    urls = asyncio.run(LinkedInPostHeadlessAdapter(settings)._discover_keyed_post_urls(limit=5))

    assert urls == (POST_URL,)


def test_headless_keyed_discovery_continues_after_provider_failure(monkeypatch) -> None:
    class FailingProvider:
        name = "Failing discovery"

        def __init__(self, settings: Settings) -> None:
            self.settings = settings

        async def discover(self, *, limit: int | None = None) -> list[LinkedInPostCandidate]:
            raise RuntimeError("provider unavailable")

    class WorkingProvider:
        name = "Working discovery"

        def __init__(self, settings: Settings) -> None:
            self.settings = settings

        async def discover(self, *, limit: int | None = None) -> list[LinkedInPostCandidate]:
            return [_candidate()]

    monkeypatch.setattr(linkedin_post_headless, "LinkedInPostSearchAdapter", FailingProvider)
    monkeypatch.setattr(linkedin_post_headless, "LinkedInPostSerperAdapter", WorkingProvider)
    settings = Settings(
        SERPAPI_API_KEY="serpapi-key",
        SERPER_API_KEY="serper-key",
        LINKEDIN_POST_HEADLESS_QUERY="custom query",
    )

    urls = asyncio.run(LinkedInPostHeadlessAdapter(settings)._discover_keyed_post_urls(limit=5))

    assert urls == (POST_URL,)


def test_headless_prioritizes_newest_candidates_across_query_families(monkeypatch) -> None:
    older_url = "https://www.linkedin.com/posts/older_activity-7435364783379341312-example"
    newer_url = "https://www.linkedin.com/posts/newer_activity-7483822807449600000-example"

    class FakeProvider:
        def __init__(self, settings: Settings) -> None:
            self.settings = settings

        async def discover(self, *, limit: int | None = None) -> list[LinkedInPostCandidate]:
            url = older_url if self.settings.linkedin_post_search_query == "older query" else newer_url
            return [_candidate(url)]

    monkeypatch.setattr(linkedin_post_headless, "LinkedInPostSearchAdapter", FakeProvider)
    settings = Settings(
        SERPAPI_API_KEY="serpapi-key",
        SERPER_API_KEY="",
        LINKEDIN_POST_HEADLESS_QUERY="older query || newer query",
    )

    urls = asyncio.run(LinkedInPostHeadlessAdapter(settings)._discover_keyed_post_urls(limit=1))

    assert urls == (newer_url,)


def test_headless_prioritizes_undated_candidate_before_known_stale_candidate(monkeypatch) -> None:
    stale_url = "https://www.linkedin.com/posts/old_activity-7435364783379341312-example"
    undated_url = "https://www.linkedin.com/posts/no-date-example"

    class FakeProvider:
        def __init__(self, settings: Settings) -> None:
            self.settings = settings

        async def discover(self, *, limit: int | None = None) -> list[LinkedInPostCandidate]:
            url = stale_url if self.settings.linkedin_post_search_query == "stale query" else undated_url
            return [_candidate(url)]

    monkeypatch.setattr(linkedin_post_headless, "LinkedInPostSearchAdapter", FakeProvider)
    monkeypatch.setattr(
        linkedin_post_headless,
        "utcnow",
        lambda: datetime(2026, 7, 19, 12, 0, tzinfo=UTC),
    )
    settings = Settings(
        SERPAPI_API_KEY="serpapi-key",
        SERPER_API_KEY="",
        LINKEDIN_POST_HEADLESS_QUERY="stale query || undated query",
        LINKEDIN_POST_MAX_AGE_HOURS=120,
    )

    urls = asyncio.run(LinkedInPostHeadlessAdapter(settings)._discover_keyed_post_urls(limit=1))

    assert urls == (undated_url,)


def test_headless_rejects_off_domain_redirect_before_reading_content() -> None:
    class FakePage:
        url = "https://evil.example/login"
        closed = False

        def set_default_timeout(self, timeout_ms: int) -> None:
            return None

        async def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
            return None

        async def content(self) -> str:
            raise AssertionError("off-domain content must not be read")

        async def close(self) -> None:
            self.closed = True

    class FakeContext:
        def __init__(self) -> None:
            self.page = FakePage()

        async def new_page(self) -> FakePage:
            return self.page

    context = FakeContext()
    adapter = LinkedInPostHeadlessAdapter(Settings())

    vacancy = asyncio.run(adapter._read_public_post(context, POST_URL, timeout_ms=1000))

    assert vacancy is None
    assert context.page.closed is True


def test_headless_uses_validated_final_linkedin_url_after_redirect() -> None:
    final_url = "https://www.linkedin.com/posts/redirected_activity-7483822807449600000-example"

    class FakePage:
        url = final_url

        def set_default_timeout(self, timeout_ms: int) -> None:
            return None

        async def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
            return None

        async def content(self) -> str:
            return '<div class="feed-shared-update-v2__description-wrapper">Hiring Python Developer</div>'

        async def title(self) -> str:
            return "Hiring Python Developer | LinkedIn"

        async def close(self) -> None:
            return None

    class FakeContext:
        async def new_page(self) -> FakePage:
            return FakePage()

    adapter = LinkedInPostHeadlessAdapter(Settings())

    vacancy = asyncio.run(adapter._read_public_post(FakeContext(), POST_URL, timeout_ms=1000))

    assert vacancy is not None
    assert vacancy.url == final_url


def test_headless_extracts_static_public_post_content_selector() -> None:
    html = """
    <html>
      <body>
        <article>
          <p class="attributed-text-segment-list__content">
            We are hiring a Backend Engineer to build Python APIs.
          </p>
        </article>
      </body>
    </html>
    """

    assert (
        linkedin_post_headless._extract_post_text(html)
        == "We are hiring a Backend Engineer to build Python APIs."
    )


def test_headless_fetch_is_fail_closed_before_playwright(monkeypatch) -> None:
    def fail_playwright():
        raise AssertionError("Playwright must not start without recorded permission")

    monkeypatch.setattr(linkedin_post_headless, "async_playwright", fail_playwright)
    adapter = LinkedInPostHeadlessAdapter(
        Settings(
            ENABLE_LINKEDIN_POST_HEADLESS=True,
            LINKEDIN_HEADLESS_ACCESS_AUTHORIZED=False,
            LINKEDIN_HEADLESS_PERMISSION_REFERENCE="",
        )
    )

    assert asyncio.run(adapter.fetch()) == []


def test_search_provider_error_does_not_expose_api_key() -> None:
    secret = "super-secret-serpapi-key"

    class FailingResponse:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        def raise_for_status(self) -> None:
            request_info = SimpleNamespace(real_url=f"https://serpapi.com/search.json?api_key={secret}")
            raise aiohttp.ClientResponseError(
                request_info=request_info,
                history=(),
                status=401,
                message="Unauthorized",
            )

    class FailingSession:
        def get(self, url: str, *, params: dict):
            return FailingResponse()

    with pytest.raises(LinkedInSearchProviderError) as exc_info:
        asyncio.run(
            _get_search_payload(
                FailingSession(),
                "https://serpapi.com/search.json",
                params={"api_key": secret},
            )
        )

    assert secret not in str(exc_info.value)
    assert exc_info.value.status_code == 401
    assert exc_info.value.failure_type == ""
    assert exc_info.value.__suppress_context__ is True
