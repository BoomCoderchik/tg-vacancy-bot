import asyncio
from datetime import UTC, datetime

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.sources.adapters.linkedin_post_search import LinkedInPostCandidate
from tg_vacancy_bot.sources.adapters.linkedin_post_guest import (
    LinkedInPostGuestAdapter,
    _discover_free_post_urls,
    _snippet_vacancy,
)


def _fresh_link(slug: str) -> str:
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    return f"https://www.linkedin.com/posts/{slug}-activity-{now_ms << 22}/"


def _pretend_now() -> datetime:
    return datetime.now(UTC)


def _post_page_html() -> str:
    return """
    <html><head><title>Hiring Junior Frontend Developer | LinkedIn</title></head>
    <body>
      <article>
        <p class="attributed-text-segment-list__content">We are hiring a junior
        frontend developer to build React interfaces.</p>
      </article>
    </body></html>
    """


def test_snippet_vacancy_keeps_guest_source_and_canonical_url() -> None:
    candidate = LinkedInPostCandidate(
        url=_fresh_link("junior-frontend"),
        search_title="Hiring Junior Frontend Developer",
        snippet="We are hiring a junior frontend developer.",
        date_text="",
        provider="bing_rss",
        query="",
    )

    vacancy = _snippet_vacancy(candidate)

    assert vacancy is not None
    assert vacancy.source == LinkedInPostGuestAdapter.name
    assert vacancy.url == candidate.url
    assert "react" not in vacancy.description.lower() or "React" in vacancy.title


def test_fetch_reads_guest_post_and_publishes_fresh_vacancy(monkeypatch) -> None:
    url = _fresh_link("junior-frontend")
    fixed_now = _pretend_now()

    async def fake_discover(settings: Settings, limit: int):
        assert settings is not None and limit > 0
        return [
            LinkedInPostCandidate(
                url=url,
                search_title="Hiring Junior Frontend Developer",
                snippet="We are hiring a junior frontend developer.",
                date_text="",
                provider="bing_rss",
                query="",
            )
        ]

    class FakeResponse:
        def __init__(self, url: str, text: str) -> None:
            self.url = url
            self._text = text

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        def raise_for_status(self) -> None:
            return None

        async def text(self) -> str:
            return self._text

    class FakeSession:
        def get(self, url: str):
            return FakeResponse(url, _post_page_html())

    def fake_source_session(**kwargs):
        class _Ctx:
            async def __aenter__(self):
                return FakeSession()

            async def __aexit__(self, *args: object) -> None:
                return None

        return _Ctx()

    monkeypatch.setattr("tg_vacancy_bot.sources.adapters.linkedin_post_guest.utcnow", lambda: _pretend_now())
    monkeypatch.setattr("tg_vacancy_bot.sources.adapters.linkedin_post_guest.POST_READ_DELAY_SECONDS", 0)
    monkeypatch.setattr("tg_vacancy_bot.sources.adapters.linkedin_post_guest.POST_READ_RETRY_DELAY_SECONDS", 0)
    monkeypatch.setattr(
        "tg_vacancy_bot.sources.adapters.linkedin_post_guest._discover_free_post_urls",
        fake_discover,
    )
    monkeypatch.setattr(
        "tg_vacancy_bot.sources.adapters.linkedin_post_guest.source_session",
        fake_source_session,
    )
    settings = Settings(
        ENABLE_LINKEDIN_POST_GUEST="true",
        LINKEDIN_POST_GUEST_RESULTS_WANTED="10",
        LINKEDIN_POST_MAX_AGE_HOURS="240",
    )
    adapter = LinkedInPostGuestAdapter(settings)

    vacancies = asyncio.run(adapter.fetch())

    assert len(vacancies) == 1
    vacancy = vacancies[0]
    assert vacancy.url.startswith("https://www.linkedin.com/posts/")
    assert vacancy.source == LinkedInPostGuestAdapter.name
    assert "React interfaces." in vacancy.description
    assert vacancy.published_at is not None


def test_fetch_falls_back_to_snippet_when_guest_read_fails(monkeypatch) -> None:
    url = _fresh_link("junior-frontend")

    async def fake_discover(settings: Settings, limit: int):
        return [
            LinkedInPostCandidate(
                url=url,
                search_title="Hiring Junior Frontend Developer",
                snippet="We are hiring a junior frontend developer.",
                date_text="",
                provider="bing_rss",
                query="",
            )
        ]

    async def failing_read(self, session, url: str):
        return None

    monkeypatch.setattr("tg_vacancy_bot.sources.adapters.linkedin_post_guest._discover_free_post_urls", fake_discover)
    settings = Settings(
        ENABLE_LINKEDIN_POST_GUEST="true",
        LINKEDIN_POST_GUEST_RESULTS_WANTED="10",
        LINKEDIN_POST_MAX_AGE_HOURS="240",
    )
    adapter = LinkedInPostGuestAdapter(settings)
    adapter._read_public_post = failing_read.__get__(adapter, LinkedInPostGuestAdapter)

    vacancies = asyncio.run(adapter.fetch())

    assert len(vacancies) == 1
    assert vacancies[0].url == url
    assert vacancies[0].source == LinkedInPostGuestAdapter.name
    assert vacancies[0].published_at is not None


def test_fetch_returns_empty_when_discovery_is_empty(monkeypatch) -> None:
    async def empty_discover(settings: Settings, limit: int):
        return ()

    monkeypatch.setattr(
        "tg_vacancy_bot.sources.adapters.linkedin_post_guest._discover_free_post_urls",
        empty_discover,
    )
    settings = Settings(
        ENABLE_LINKEDIN_POST_GUEST="true",
        LINKEDIN_POST_GUEST_RESULTS_WANTED="10",
        LINKEDIN_POST_MAX_AGE_HOURS="240",
    )
    adapter = LinkedInPostGuestAdapter(settings)

    assert asyncio.run(adapter.fetch()) == []


def test_discover_free_post_urls_returns_empty_for_zero_limit() -> None:
    settings = Settings(ENABLE_LINKEDIN_POST_GUEST="true")

    assert asyncio.run(_discover_free_post_urls(settings, 0)) == ()