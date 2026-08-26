import asyncio
import base64
from datetime import UTC, datetime
from types import SimpleNamespace
from contextlib import asynccontextmanager
from urllib.parse import urlencode

import aiohttp
import pytest

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.sources.adapters import linkedin_post_headless, linkedin_post_search
from tg_vacancy_bot.sources.adapters.linkedin_post_headless import LinkedInPostHeadlessAdapter
from tg_vacancy_bot.sources.adapters.linkedin_post_search import (
    BACKOFF_DELAYS_SECONDS,
    LinkedInPostCandidate,
    _canonicalize_linkedin_post_url,
    _get_search_payload,
    _google_recency_filter,
    _result_to_candidate,
    LinkedInSearchProviderError,
    LinkedInPostSearchAdapter,
)
from tg_vacancy_bot.sources.linkedin_search_profile import (
    DEFAULT_SEARCH_INTENTS,
    fair_query_limits,
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
        provider="Keyed search",
        query="site:linkedin.com/posts developer",
    )

    assert candidate == LinkedInPostCandidate(
        url=POST_URL,
        search_title="",
        snippet="",
        date_text="",
        provider="Keyed search",
        query="site:linkedin.com/posts developer",
    )


@pytest.mark.parametrize(
    ("max_age_hours", "expected"),
    [
        (1, "qdr:h"),
        (24, "qdr:d"),
        (25, "qdr:w"),
        (240, "qdr:m"),
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
        LINKEDIN_POST_MAX_AGE_HOURS=240,
    )

    assert asyncio.run(LinkedInPostSearchAdapter(settings).discover(limit=2)) == []
    assert captured_params == [
        {
            "engine": "google",
            "api_key": "test-key",
            "q": "custom query",
            "num": 2,
            "hl": "ru",
            "tbs": "qdr:m",
        }
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
        SERPAPI_API_KEY="test-key",
    )

    urls = asyncio.run(LinkedInPostHeadlessAdapter(settings)._discover_keyed_post_urls(limit=5))

    expected_intents = select_cycle_intents(
        DEFAULT_SEARCH_INTENTS,
        max_intents=6,
        cycle_index=linkedin_post_headless._search_cycle_index(current_time),
    )
    discovery_budget = max(5, len(expected_intents))
    expected_limits = fair_query_limits(discovery_budget, expected_intents)
    assert tuple(candidate.url for candidate in urls) == (POST_URL,)
    assert calls == [
        (limit, intent.query)
        for limit, intent in zip(expected_limits, expected_intents, strict=True)
        if limit > 0
    ]


def test_headless_keyed_discovery_deduplicates_urls(monkeypatch) -> None:
    class FakeProvider:
        def __init__(self, settings: Settings) -> None:
            self.settings = settings

        async def discover(self, *, limit: int | None = None) -> list[LinkedInPostCandidate]:
            return [_candidate(), _candidate()]

    monkeypatch.setattr(linkedin_post_headless, "LinkedInPostSearchAdapter", FakeProvider)
    settings = Settings(
        SERPAPI_API_KEY="serpapi-key",
        LINKEDIN_POST_HEADLESS_QUERY="custom query",
    )

    urls = asyncio.run(LinkedInPostHeadlessAdapter(settings)._discover_keyed_post_urls(limit=5))

    assert tuple(candidate.url for candidate in urls) == (POST_URL,)


def test_headless_keyed_discovery_survives_provider_failure(monkeypatch) -> None:
    class FailingProvider:
        name = "Failing discovery"

        def __init__(self, settings: Settings) -> None:
            self.settings = settings

        async def discover(self, *, limit: int | None = None) -> list[LinkedInPostCandidate]:
            raise RuntimeError("provider unavailable")

    monkeypatch.setattr(linkedin_post_headless, "LinkedInPostSearchAdapter", FailingProvider)
    settings = Settings(
        SERPAPI_API_KEY="serpapi-key",
        LINKEDIN_POST_HEADLESS_QUERY="custom query",
    )

    urls = asyncio.run(LinkedInPostHeadlessAdapter(settings)._discover_keyed_post_urls(limit=5))

    assert urls == ()


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
        LINKEDIN_POST_HEADLESS_QUERY="older query || newer query",
    )

    urls = asyncio.run(LinkedInPostHeadlessAdapter(settings)._discover_keyed_post_urls(limit=1))

    assert tuple(candidate.url for candidate in urls) == (newer_url,)


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
        LINKEDIN_POST_HEADLESS_QUERY="stale query || undated query",
        LINKEDIN_POST_MAX_AGE_HOURS=240,
    )

    urls = asyncio.run(LinkedInPostHeadlessAdapter(settings)._discover_keyed_post_urls(limit=1))

    assert tuple(candidate.url for candidate in urls) == (undated_url,)


def test_headless_rejects_off_domain_redirect_before_reading_content(monkeypatch) -> None:
    monkeypatch.setattr(linkedin_post_headless, "POST_READ_RETRY_DELAY_SECONDS", 0)

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


def test_headless_retries_alternate_feed_update_url_after_login_redirect(monkeypatch) -> None:
    monkeypatch.setattr(linkedin_post_headless, "POST_READ_RETRY_DELAY_SECONDS", 0)
    activity_id = "7483822807449600000"
    post_html = (
        '<article><p class="attributed-text-segment-list__content">'
        "We are hiring a Junior Frontend Developer to build React UI.</p></article>"
    )
    steps = [
        (
            "https://www.linkedin.com/uas/login?session_redirect=%2Fposts%2Fexample",
            "<html>Sign in to LinkedIn</html>",
        ),
        (
            f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}/",
            post_html,
        ),
    ]

    class ScriptedPage:
        def __init__(self) -> None:
            self.calls: list[str] = []
            self.current = steps[0]

        def set_default_timeout(self, timeout_ms: int) -> None:
            return None

        async def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
            self.calls.append(url)
            index = min(len(self.calls) - 1, len(steps) - 1)
            self.current = steps[index]

        @property
        def url(self) -> str:
            return self.current[0]

        async def content(self) -> str:
            return self.current[1]

        async def title(self) -> str:
            return "Hiring Junior Frontend Developer | LinkedIn"

        async def close(self) -> None:
            return None

    class FakeContext:
        def __init__(self, page: ScriptedPage) -> None:
            self.page = page

        async def new_page(self) -> ScriptedPage:
            return self.page

    page = ScriptedPage()
    adapter = LinkedInPostHeadlessAdapter(Settings())

    vacancy = asyncio.run(
        adapter._read_public_post(FakeContext(page), POST_URL, timeout_ms=1000)
    )

    assert vacancy is not None
    assert page.calls == [
        POST_URL,
        f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}/",
    ]


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


def _client_response_error(status: int) -> aiohttp.ClientResponseError:
    return aiohttp.ClientResponseError(
        request_info=SimpleNamespace(real_url="https://serpapi.com/search.json"),
        history=(),
        status=status,
        message="provider rejected request",
    )


class _JsonResponse:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    async def __aenter__(self) -> "_JsonResponse":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    async def json(self) -> object:
        return self._payload


class ScriptedSession:
    """Session replaying scripted outcomes in order for GET and POST calls."""

    def __init__(self, *outcomes: object) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def get(self, url: str, *, params: dict | None = None):
        return self._next()

    def post(self, url: str, *, json: dict | None = None):
        return self._next()

    def _next(self):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return _JsonResponse(outcome)


def _record_backoff_sleep(monkeypatch) -> list[float]:
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(linkedin_post_search, "asyncio", SimpleNamespace(sleep=fake_sleep))
    return delays


def test_get_search_payload_retries_429_twice_then_succeeds(monkeypatch) -> None:
    delays = _record_backoff_sleep(monkeypatch)
    session = ScriptedSession(
        _client_response_error(429),
        _client_response_error(429),
        {"organic_results": []},
    )

    payload = asyncio.run(
        _get_search_payload(
            session,
            "https://serpapi.com/search.json",
            params={"api_key": "test-key"},
        )
    )

    assert payload == {"organic_results": []}
    assert session.calls == 3
    assert delays == list(BACKOFF_DELAYS_SECONDS)


def test_get_search_payload_raises_after_three_429_responses(monkeypatch) -> None:
    delays = _record_backoff_sleep(monkeypatch)
    session = ScriptedSession(
        _client_response_error(429),
        _client_response_error(429),
        _client_response_error(429),
    )

    with pytest.raises(LinkedInSearchProviderError) as exc_info:
        asyncio.run(
            _get_search_payload(
                session,
                "https://serpapi.com/search.json",
                params={"api_key": "test-key"},
            )
        )

    assert exc_info.value.status_code == 429
    assert exc_info.value.failure_type == ""
    assert session.calls == 3
    assert delays == list(BACKOFF_DELAYS_SECONDS)


def test_get_search_payload_does_not_retry_client_4xx_errors(monkeypatch) -> None:
    delays = _record_backoff_sleep(monkeypatch)
    session = ScriptedSession(_client_response_error(400))

    with pytest.raises(LinkedInSearchProviderError) as exc_info:
        asyncio.run(
            _get_search_payload(
                session,
                "https://serpapi.com/search.json",
                params={"api_key": "test-key"},
            )
        )

    assert exc_info.value.status_code == 400
    assert session.calls == 1
    assert delays == []


def test_get_search_payload_retries_network_errors_then_succeeds(monkeypatch) -> None:
    delays = _record_backoff_sleep(monkeypatch)
    session = ScriptedSession(
        aiohttp.ClientError("connection reset"),
        aiohttp.ClientError("connection reset"),
        {"organic_results": []},
    )

    payload = asyncio.run(
        _get_search_payload(session, "https://serpapi.com/search.json", params={"q": "test"})
    )

    assert payload == {"organic_results": []}
    assert session.calls == 3
    assert delays == list(BACKOFF_DELAYS_SECONDS)


def _rss_feed(*items: str) -> str:
    body = "".join(f"<item>{item}</item>" for item in items)
    return f"<rss><channel>{body}</channel></rss>"


def _bing_html_with_ck_links(*targets: str) -> str:
    blocks = []
    for index, target in enumerate(targets):
        encoded = base64.urlsafe_b64encode(target.encode()).decode().rstrip("=")
        href = f"https://www.bing.com/ck/a?!&&p=p{index}&u=a1{encoded}&ntb=1"
        blocks.append(
            f'<li class="b_algo"><h2><a href="{href}">Hiring</a></h2>'
            "<div class='b_caption'><p>We are hiring a developer.</p></div></li>"
        )
    return f"<html><body><ol id='b_results'>{''.join(blocks)}</ol></body></html>"


def test_decode_bing_redirect_url_returns_real_target() -> None:
    target = "https://www.linkedin.com/posts/hiring_activity-7483822807449600000-abcd"
    encoded = base64.urlsafe_b64encode(target.encode()).decode().rstrip("=")

    assert (
        linkedin_post_headless._decode_bing_redirect_url(
            f"https://www.bing.com/ck/a?!&&p=xyz&u=a1{encoded}&ntb=1"
        )
        == target
    )
    assert (
        linkedin_post_headless._decode_bing_redirect_url("https://www.linkedin.com/posts/direct")
        == "https://www.linkedin.com/posts/direct"
    )
    assert linkedin_post_headless._decode_bing_redirect_url("https://www.bing.com/ck/a?p=1") == ""


def test_rss_post_results_keep_raw_items_without_snippet_or_date() -> None:
    feed = _rss_feed(
        "<title>Hiring Junior Frontend Developer</title>"
        "<link>https://www.linkedin.com/posts/alpha_activity-7483822807449600000-abcd</link>"
        "<pubDate>Tue, 18 Aug 2026 10:00:00 GMT</pubDate>",
        "<link>https://www.linkedin.com/posts/beta_activity-7483822807449600001-efgh</link>",
    )

    results = linkedin_post_headless._rss_post_results(feed)

    assert [result.link for result in results] == [
        "https://www.linkedin.com/posts/alpha_activity-7483822807449600000-abcd",
        "https://www.linkedin.com/posts/beta_activity-7483822807449600001-efgh",
    ]
    assert results[0].date_text.startswith("Tue, 18 Aug 2026")
    assert results[1].date_text == ""
    assert linkedin_post_headless._rss_post_results("<not-rss>") == []


class FakeSearchResponse:
    def __init__(self, text: str) -> None:
        self._text = text

    async def __aenter__(self) -> "FakeSearchResponse":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    async def text(self) -> str:
        return self._text


class FakeSearchSession:
    """Serves canned bodies by URL+params predicate, like real aiohttp calls."""

    def __init__(self, routes: tuple[tuple[str, str], ...]) -> None:
        self.routes = routes
        self.calls: list[tuple[str, dict]] = []
        self.post_calls: list[tuple[str, dict]] = []

    def get(self, url: str, params: dict | None = None):
        resolved_params = dict(params or {})
        self.calls.append((url, resolved_params))
        return self._resolve(url, resolved_params)

    def post(self, url: str, params: dict | None = None, data: dict | None = None):
        resolved = dict(params or {})
        resolved.update(data or {})
        self.post_calls.append((url, resolved))
        return self._resolve(url, resolved)

    def _resolve(self, url: str, resolved_params: dict):
        haystack = url + "?" + urlencode(resolved_params)
        for marker, text in self.routes:
            if marker in haystack:
                return FakeSearchResponse(text)
        return FakeSearchResponse("")


def _free_discovery_settings() -> Settings:
    return Settings(LINKEDIN_POST_HEADLESS_QUERY="", LINKEDIN_HEADLESS_DISCOVERY_PAGES="3")


def test_discover_free_post_urls_collects_dedupes_and_prioritizes_dated(monkeypatch) -> None:
    monkeypatch.setattr(linkedin_post_headless, "SEARCH_PAGE_DELAY_SECONDS", 0)
    alpha = "https://www.linkedin.com/posts/alpha_activity-7483822807449600000-abcd"
    beta = "https://www.linkedin.com/posts/beta_activity-7483822807449600001-efgh"
    gamma = "https://de.linkedin.com/posts/gamma_activity-7483822807449600002-ijkl"
    delta = "https://www.linkedin.com/posts/delta_activity-7483822807449600003-mnop"
    ddg_html = (
        "<html><body>"
        "<a class='result__a' href='//duckduckgo.com/l/?uddg="
        f"https%3A%2F%2Fwww.linkedin.com%2Fposts%2Fbeta_activity-7483822807449600001-efgh"
        "'>dup</a>"
        f"<a class='result__a' href='{gamma}'>new</a>"
        "</body></html>"
    )
    session = FakeSearchSession(
        (
            ("format=rss", _rss_feed(
                f"<title>Hiring Junior Frontend Developer</title><link>{alpha}</link>"
                "<pubDate>Tue, 18 Aug 2026 10:00:00 GMT</pubDate>",
                f"<link>{beta}</link>",
            )),
            ("duckduckgo", ddg_html),
            ("first=11", ""),
            ("bing.com/search", _bing_html_with_ck_links(delta)),
        )
    )
    monkeypatch.setattr(linkedin_post_headless, "source_session", lambda **kwargs: _fake_session_context(session))

    urls = asyncio.run(
        linkedin_post_headless.LinkedInPostHeadlessAdapter(_free_discovery_settings())._discover_free_post_urls(limit=4)
    )

    canonical_gamma = "https://www.linkedin.com/posts/gamma_activity-7483822807449600002-ijkl"
    # alpha carries the explicit RSS pubDate and wins; the other three share
    # one activity-ID timestamp (the IDs differ below bit 22), so the stable
    # URL-descending tie-break orders them.
    assert tuple(candidate.url for candidate in urls) == (alpha, canonical_gamma, delta, beta)


def test_discover_free_post_urls_skips_challenge_provider(monkeypatch) -> None:
    monkeypatch.setattr(linkedin_post_headless, "SEARCH_PAGE_DELAY_SECONDS", 0)
    delta = "https://www.linkedin.com/posts/delta_activity-7483822807449600003-mnop"
    session = FakeSearchSession(
        (
            ("format=rss", ""),
            ("duckduckgo", "<html>unusual traffic from your computer network</html>"),
            ("bing.com/search", _bing_html_with_ck_links(delta)),
        )
    )
    monkeypatch.setattr(linkedin_post_headless, "source_session", lambda **kwargs: _fake_session_context(session))

    urls = asyncio.run(
        linkedin_post_headless.LinkedInPostHeadlessAdapter(_free_discovery_settings())._discover_free_post_urls(limit=4)
    )

    assert tuple(candidate.url for candidate in urls) == (delta,)


class FakeBrowserPage:
    """Scripted Playwright page: each goto consumes one canned response."""

    def __init__(self, responses: list[tuple[str, str]]) -> None:
        self.responses = responses
        self.calls: list[str] = []
        self.url = "https://www.bing.com/"

    def set_default_timeout(self, timeout_ms: int) -> None:
        return None

    async def goto(self, url: str, wait_until: str | None = None, timeout: int | None = None):
        self.calls.append(url)
        index = min(len(self.calls) - 1, len(self.responses) - 1)
        final_url, html = self.responses[index]
        self.url = final_url or url
        return html

    async def content(self) -> str:
        index = min(len(self.calls) - 1, len(self.responses) - 1)
        return self.responses[index][1]

    async def close(self) -> None:
        return None


class FakeBrowserContext:
    def __init__(self, page: FakeBrowserPage) -> None:
        self.page = page

    async def new_page(self) -> FakeBrowserPage:
        return self.page

    async def close(self) -> None:
        return None


def _single_intent_settings() -> Settings:
    return Settings(
        LINKEDIN_POST_HEADLESS_QUERY="site:linkedin.com/posts test",
        LINKEDIN_HEADLESS_DISCOVERY_PAGES="3",
    )


def test_discover_browser_post_urls_collects_dedupes_and_stops_paginating(monkeypatch) -> None:
    monkeypatch.setattr(linkedin_post_headless, "SEARCH_PAGE_DELAY_SECONDS", 0)
    alpha = "https://www.linkedin.com/posts/alpha_activity-7483822807449600000-abcd"
    page = FakeBrowserPage(
        [
            ("", _bing_html_with_ck_links(alpha)),
            ("", _bing_html_with_ck_links(alpha)),  # repeat page: no new urls
            ("", _bing_html_with_ck_links(alpha)),
        ]
    )

    urls = asyncio.run(
        LinkedInPostHeadlessAdapter(_single_intent_settings())._discover_browser_post_urls(
            FakeBrowserContext(page),
            limit=4,
        )
    )

    assert tuple(candidate.url for candidate in urls) == (alpha,)
    # The second result page repeated the same URL, so pagination stopped
    # before the third page request.
    assert len(page.calls) == 2
    assert all(call.startswith("https://www.bing.com/search?") for call in page.calls)
    assert "first=1&setlang=en" in page.calls[0]
    assert "first=11&setlang=en" in page.calls[1]


def test_discover_browser_post_urls_skips_challenge_page(monkeypatch) -> None:
    monkeypatch.setattr(linkedin_post_headless, "SEARCH_PAGE_DELAY_SECONDS", 0)
    delta = "https://www.linkedin.com/posts/delta_activity-7483822807449600003-mnop"
    challenge_then_success = Settings(
        LINKEDIN_POST_HEADLESS_QUERY="site:linkedin.com/posts one || site:linkedin.com/posts two",
        LINKEDIN_HEADLESS_DISCOVERY_PAGES="3",
    )
    page = FakeBrowserPage(
        [
            ("", "<html>unusual traffic from your computer network</html>"),
            ("", _bing_html_with_ck_links(delta)),
        ]
    )

    urls = asyncio.run(
        LinkedInPostHeadlessAdapter(challenge_then_success)._discover_browser_post_urls(
            FakeBrowserContext(page),
            limit=4,
        )
    )

    assert tuple(candidate.url for candidate in urls) == (delta,)
    # Intent one hit the challenge and stopped. Intent two read its first
    # result page, then requested page two which repeated the same URL and
    # stopped pagination.
    assert len(page.calls) == 3


def test_discover_browser_post_urls_skips_off_domain_redirect(monkeypatch) -> None:
    monkeypatch.setattr(linkedin_post_headless, "SEARCH_PAGE_DELAY_SECONDS", 0)
    off_domain_then_empty = Settings(
        LINKEDIN_POST_HEADLESS_QUERY="site:linkedin.com/posts one || site:linkedin.com/posts two",
        LINKEDIN_HEADLESS_DISCOVERY_PAGES="3",
    )
    page = FakeBrowserPage(
        [
            ("https://login.example.com/redirect", "<html>sign in</html>"),
            ("", ""),
        ]
    )

    urls = asyncio.run(
        LinkedInPostHeadlessAdapter(off_domain_then_empty)._discover_browser_post_urls(
            FakeBrowserContext(page),
            limit=4,
        )
    )

    assert urls == ()


def test_fetch_falls_back_to_browser_discovery(monkeypatch) -> None:
    settings = Settings(
        ENABLE_LINKEDIN_POST_HEADLESS=True,
        LINKEDIN_HEADLESS_ACCESS_AUTHORIZED=True,
        LINKEDIN_HEADLESS_PERMISSION_REFERENCE="test-reference",
    )
    adapter = LinkedInPostHeadlessAdapter(settings)

    async def empty_keyed(limit: int):
        return ()

    async def empty_free(limit: int):
        return ()

    discovered: list[tuple[object, int]] = []

    async def browser_discovery(context, limit: int):
        discovered.append((context, limit))
        return (_candidate(),)

    read_urls: list[str] = []

    async def fake_read(context, url: str, timeout_ms: int):
        read_urls.append(url)
        return None

    monkeypatch.setattr(adapter, "_discover_keyed_post_urls", empty_keyed)
    monkeypatch.setattr(adapter, "_discover_free_post_urls", empty_free)
    monkeypatch.setattr(adapter, "_discover_browser_post_urls", browser_discovery)
    monkeypatch.setattr(adapter, "_read_public_post", fake_read)
    monkeypatch.setattr(linkedin_post_headless, "async_playwright", _fake_playwright_factory)

    vacancies = asyncio.run(adapter.fetch())

    assert vacancies == []
    assert len(discovered) == 1
    assert isinstance(discovered[0][0], FakeBrowserContext)
    assert read_urls == [POST_URL]


def test_fetch_launches_chromium_without_automation_flag(monkeypatch) -> None:
    settings = Settings(
        ENABLE_LINKEDIN_POST_HEADLESS=True,
        LINKEDIN_HEADLESS_ACCESS_AUTHORIZED=True,
        LINKEDIN_HEADLESS_PERMISSION_REFERENCE="test-reference",
    )
    adapter = LinkedInPostHeadlessAdapter(settings)

    async def empty(limit: int):
        return ()

    async def fake_read(context, url: str, timeout_ms: int):
        return None

    launch_calls: list[dict] = []
    monkeypatch.setattr(adapter, "_discover_keyed_post_urls", empty)
    monkeypatch.setattr(adapter, "_discover_free_post_urls", empty)
    monkeypatch.setattr(adapter, "_read_public_post", fake_read)
    monkeypatch.setattr(
        linkedin_post_headless,
        "async_playwright",
        lambda: _fake_playwright_factory(launch_calls),
    )

    asyncio.run(adapter.fetch())

    assert len(launch_calls) == 1
    args = launch_calls[0].get("args")
    assert args is not None
    assert "--disable-blink-features=AutomationControlled" in args


def test_fetch_paces_sequential_post_reads(monkeypatch) -> None:
    monkeypatch.setattr(linkedin_post_headless, "POST_READ_DELAY_SECONDS", 0)
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(linkedin_post_headless.asyncio, "sleep", fake_sleep)
    settings = Settings(
        ENABLE_LINKEDIN_POST_HEADLESS=True,
        LINKEDIN_HEADLESS_ACCESS_AUTHORIZED=True,
        LINKEDIN_HEADLESS_PERMISSION_REFERENCE="test-reference",
    )
    adapter = LinkedInPostHeadlessAdapter(settings)

    second_url = "https://www.linkedin.com/posts/second_activity-7483822807449600001-example"

    async def two_urls(limit: int):
        return (_candidate(), _candidate(second_url))

    read_urls: list[str] = []

    async def fake_read(context, url: str, timeout_ms: int):
        read_urls.append(url)
        return None

    async def empty(limit: int):
        return ()

    monkeypatch.setattr(adapter, "_discover_keyed_post_urls", empty)
    monkeypatch.setattr(adapter, "_discover_free_post_urls", two_urls)
    monkeypatch.setattr(adapter, "_read_public_post", fake_read)
    monkeypatch.setattr(linkedin_post_headless, "async_playwright", _fake_playwright_factory)

    asyncio.run(adapter.fetch())

    assert read_urls == [POST_URL, second_url]
    # Each phase (HTTP-first pass, then the browser fallback for the pending
    # candidates) paces its sequential reads with one inter-candidate pause.
    assert delays == [0.0, 0.0]


def test_fetch_publishes_search_snippet_when_guest_read_is_blocked(monkeypatch) -> None:
    monkeypatch.setattr(linkedin_post_headless, "POST_READ_DELAY_SECONDS", 0)
    fixed_now = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(linkedin_post_headless, "utcnow", lambda: fixed_now)
    settings = Settings(
        ENABLE_LINKEDIN_POST_HEADLESS=True,
        LINKEDIN_HEADLESS_ACCESS_AUTHORIZED=True,
        LINKEDIN_HEADLESS_PERMISSION_REFERENCE="test-reference",
    )
    adapter = LinkedInPostHeadlessAdapter(settings)

    discovered_candidate = LinkedInPostCandidate(
        url=POST_URL,
        search_title="Hiring Junior Frontend Developer | LinkedIn",
        snippet="We are hiring a junior frontend developer to build React interfaces.",
        date_text="",
        provider="duckduckgo",
        query="site:linkedin.com/posts hiring",
    )

    async def free_discovery(limit: int):
        return (discovered_candidate,)

    async def empty(limit: int):
        return ()

    async def blocked_read(context, url: str, timeout_ms: int):
        return None

    read_urls: list[str] = []
    original_read = blocked_read

    async def recording_read(context, url: str, timeout_ms: int):
        read_urls.append(url)
        return await original_read(context, url, timeout_ms)

    monkeypatch.setattr(adapter, "_discover_keyed_post_urls", empty)
    monkeypatch.setattr(adapter, "_discover_free_post_urls", free_discovery)
    monkeypatch.setattr(adapter, "_read_public_post", recording_read)
    monkeypatch.setattr(linkedin_post_headless, "async_playwright", _fake_playwright_factory)

    vacancies = asyncio.run(adapter.fetch())

    assert len(vacancies) == 1
    assert vacancies[0].url == POST_URL
    assert vacancies[0].source == adapter.name
    assert "junior frontend developer" in vacancies[0].description.lower()
    assert read_urls == [POST_URL]


async def _fake_noop() -> None:
    return None


@asynccontextmanager
async def _fake_playwright_factory(launch_calls: list[dict] | None = None):
    async def launch(*args: object, **kwargs: object):
        if launch_calls is not None:
            launch_calls.append(kwargs)
        return SimpleNamespace(new_context=_fake_new_context, close=_fake_noop)

    yield SimpleNamespace(
        chromium=SimpleNamespace(
            launch=launch,
        )
    )


async def _fake_launch(headless: bool, args: list[str] | None = None):
    return SimpleNamespace(new_context=_fake_new_context, close=_fake_noop)


async def _fake_new_context(**kwargs: object):
    return FakeBrowserContext(FakeBrowserPage([]))


@asynccontextmanager
async def _fake_session_context(session: FakeSearchSession):
    yield session
