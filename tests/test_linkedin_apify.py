import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.sources.adapters import linkedin_post_apify
from tg_vacancy_bot.sources.adapters.linkedin_post_apify import LinkedInPostApifyAdapter, _item_to_vacancy


POST_URL = "https://www.linkedin.com/posts/example_activity-7483822807449600000-example"


class FakeResponse:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def json(self, **_kwargs):
        return self.payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def post(self, url, *, params, json):
        self.calls.append((url, params, json))
        return FakeResponse(self.payload)


def _item(*, content: str, url: str = POST_URL, published_at: datetime | None = None) -> dict:
    return {
        "linkedinUrl": url,
        "content": content,
        "author": {"name": "Hiring Manager"},
        "postedAt": {"date": (published_at or datetime.now(UTC) - timedelta(hours=1)).isoformat()},
    }


def test_item_to_vacancy_requires_hiring_intent_and_development_role() -> None:
    vacancy = _item_to_vacancy(
        _item(content="We are hiring a Senior Front-End Developer to join our team."),
        source="Apify",
    )

    assert vacancy is not None
    assert vacancy.url == POST_URL
    assert "Front-End Developer" in vacancy.title
    assert vacancy.published_at is not None

    assert _item_to_vacancy(
        _item(content="We are hiring a recruiter for our growing team."),
        source="Apify",
    ) is None
    assert _item_to_vacancy(
        _item(content="Our frontend developer shared a technical article."),
        source="Apify",
    ) is None


def test_apify_adapter_runs_actor_and_maps_full_post_content(monkeypatch) -> None:
    session = FakeSession(
        [
            _item(content="Ищем backend разработчика в команду. Python и FastAPI."),
            _item(content="Ищем backend разработчика в команду. Python и FastAPI.", url=POST_URL),
        ]
    )

    @asynccontextmanager
    async def fake_source_session(*_args, **_kwargs):
        yield session

    monkeypatch.setattr(linkedin_post_apify, "source_session", fake_source_session)
    settings = Settings(
        ENABLE_LINKEDIN_POST_APIFY=True,
        APIFY_API_TOKEN="apify-secret",
        LINKEDIN_POST_APIFY_SEARCH_QUERIES="Hiring frontend developer||Ищем backend разработчика",
        LINKEDIN_POST_APIFY_MAX_POSTS=7,
        LINKEDIN_POST_APIFY_POSTED_LIMIT="24h",
    )

    vacancies = asyncio.run(LinkedInPostApifyAdapter(settings).fetch())

    assert len(vacancies) == 1
    assert vacancies[0].description.startswith("Ищем backend")
    assert session.calls[0][1] == {
        "timeout": "240",
        "format": "json",
        "clean": "1",
        "maxItems": "14",
    }
    assert session.calls[0][2] == {
        "searchQueries": ["Hiring frontend developer", "Ищем backend разработчика"],
        "postedLimit": "24h",
        "sortBy": "date",
        "maxPosts": 7,
    }


def test_apify_adapter_rejects_queries_longer_than_actor_limit() -> None:
    settings = Settings(
        ENABLE_LINKEDIN_POST_APIFY=True,
        APIFY_API_TOKEN="apify-secret",
        LINKEDIN_POST_APIFY_SEARCH_QUERIES="x" * 86,
    )

    try:
        asyncio.run(LinkedInPostApifyAdapter(settings).fetch())
    except ValueError as exc:
        assert "85 characters" in str(exc)
    else:
        raise AssertionError("Expected query-length validation to fail")
