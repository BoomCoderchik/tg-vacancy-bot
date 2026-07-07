from datetime import UTC, datetime, timedelta
import asyncio

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.linkedin_posts import (
    build_linkedin_user_post_vacancy,
    classify_linkedin_user_post,
)
from tg_vacancy_bot.sources.adapters.linkedin_user_posts import LinkedInUserPostsAdapter


def test_classify_linkedin_user_post_allows_explicit_hiring_intent() -> None:
    role = classify_linkedin_user_post(
        "We're hiring a React developer to join our product team. DM me for details."
    )

    assert role == "React developer"


def test_classify_linkedin_user_post_rejects_posts_without_hiring_intent() -> None:
    assert classify_linkedin_user_post("Thoughts on hiring backend engineers in 2026.") is None


def test_classify_linkedin_user_post_rejects_candidate_posts() -> None:
    assert classify_linkedin_user_post("Looking for job as a frontend developer, open to work.") is None


def test_classify_linkedin_user_post_detects_designer_role() -> None:
    role = classify_linkedin_user_post("We need a UI/UX designer for a fintech app.")

    assert role == "UI/UX designer"


def test_build_linkedin_user_post_vacancy_requires_url() -> None:
    vacancy = build_linkedin_user_post_vacancy(
        {
            "text": "Looking for a backend engineer to join our team.",
        },
        now=datetime(2026, 7, 7, 8, tzinfo=UTC),
    )

    assert vacancy is None


def test_build_linkedin_user_post_vacancy_maps_relevant_post() -> None:
    now = datetime(2026, 7, 7, 8, tzinfo=UTC)
    vacancy = build_linkedin_user_post_vacancy(
        {
            "url": "https://www.linkedin.com/feed/update/urn:li:activity:123/",
            "text": "Looking for a backend engineer to join our team.",
            "published_at": "2026-07-07T07:30:00+00:00",
            "author": "Jane Hiring",
        },
        now=now,
    )

    assert vacancy is not None
    assert vacancy.result_type == "linkedin_user_post"
    assert vacancy.title == "Looking for a backend engineer to join our team."
    assert vacancy.role == "backend engineer"
    assert vacancy.company == "Jane Hiring"
    assert vacancy.url == "https://www.linkedin.com/feed/update/urn:li:activity:123/"
    assert vacancy.published_at == datetime(2026, 7, 7, 7, 30, tzinfo=UTC)
    assert vacancy.detected_at == now


def test_build_linkedin_user_post_vacancy_rejects_stale_records_when_requested() -> None:
    now = datetime(2026, 7, 7, 8, tzinfo=UTC)
    vacancy = build_linkedin_user_post_vacancy(
        {
            "url": "https://www.linkedin.com/feed/update/urn:li:activity:old/",
            "text": "Hiring Python developer for a remote team.",
            "published_at": (now - timedelta(hours=72)).isoformat(),
        },
        now=now,
        max_age_hours=48,
    )

    assert vacancy is None


def test_linkedin_user_posts_adapter_fetches_and_filters_configured_feed(monkeypatch) -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        LINKEDIN_USER_POSTS_FEED_URL="https://authorized.example/linkedin-posts.json",
        SOURCE_MAX_AGE_HOURS="48",
    )

    class FakeResponse:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def raise_for_status(self) -> None:
            return None

        async def json(self):
            return {
                "posts": [
                    {
                        "url": "https://www.linkedin.com/feed/update/urn:li:activity:123/",
                        "text": "We're hiring a React developer to join our team.",
                    },
                    {
                        "url": "https://www.linkedin.com/feed/update/urn:li:activity:456/",
                        "text": "Looking for job as a React developer.",
                    },
                ]
            }

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def get(self, url):
            assert url == "https://authorized.example/linkedin-posts.json"
            return FakeResponse()

    monkeypatch.setattr(
        "tg_vacancy_bot.sources.adapters.linkedin_user_posts.source_session",
        lambda: FakeSession(),
    )

    vacancies = asyncio.run(LinkedInUserPostsAdapter(settings).fetch())

    assert [vacancy.role for vacancy in vacancies] == ["React developer"]
    assert vacancies[0].result_type == "linkedin_user_post"
