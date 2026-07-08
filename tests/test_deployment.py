import asyncio

import pytest
from aiohttp.test_utils import TestClient, TestServer

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.deployment import create_web_app, get_port, health


def test_get_port_uses_platform_port(monkeypatch) -> None:
    monkeypatch.setenv("PORT", "9000")

    assert get_port() == 9000


def test_get_port_rejects_non_integer(monkeypatch) -> None:
    monkeypatch.setenv("PORT", "not-a-port")

    with pytest.raises(RuntimeError, match="PORT must be an integer"):
        get_port()


def test_health_returns_ok() -> None:
    response = asyncio.run(health(None))

    assert response.status == 200
    assert response.text == '{"status": "ok"}'


def test_linkedin_user_posts_webhook_requires_enabled_token() -> None:
    settings = Settings(TELEGRAM_BOT_TOKEN="token", TARGET_CHAT_ID="@target")

    async def run() -> tuple[int, dict]:
        app = create_web_app(settings, publisher=lambda vacancies: _publish_count(vacancies))
        async with TestServer(app) as server:
            async with TestClient(server) as client:
                response = await client.post("/linkedin/user-posts", json={})
                return response.status, await response.json()

    status, payload = asyncio.run(run())

    assert status == 404
    assert payload == {"error": "linkedin webhook is not enabled"}


def test_linkedin_user_posts_webhook_rejects_bad_token() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        LINKEDIN_USER_POSTS_WEBHOOK_TOKEN="secret",
    )

    async def run() -> tuple[int, dict]:
        app = create_web_app(settings, publisher=lambda vacancies: _publish_count(vacancies))
        async with TestServer(app) as server:
            async with TestClient(server) as client:
                response = await client.post(
                    "/linkedin/user-posts",
                    json={},
                    headers={"Authorization": "Bearer wrong"},
                )
                return response.status, await response.json()

    status, payload = asyncio.run(run())

    assert status == 401
    assert payload == {"error": "unauthorized"}


def test_linkedin_user_posts_webhook_publishes_relevant_post() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        LINKEDIN_USER_POSTS_WEBHOOK_TOKEN="secret",
    )
    published_titles: list[str] = []

    async def publisher(vacancies):
        published_titles.extend(vacancy.title for vacancy in vacancies)
        return len(vacancies)

    async def run() -> tuple[int, dict]:
        app = create_web_app(settings, publisher=publisher)
        async with TestServer(app) as server:
            async with TestClient(server) as client:
                response = await client.post(
                    "/linkedin/user-posts",
                    json={
                        "posts": [
                            {
                                "url": "https://www.linkedin.com/posts/example",
                                "text": (
                                    "\u0418\u0449\u0435\u043c Junior Front-End Developer "
                                    "\u0432 \u043a\u043e\u043c\u0430\u043d\u0434\u0443 DAP. "
                                    "Angular, TypeScript, HTML/CSS, REST API."
                                ),
                            },
                            {
                                "url": "https://www.linkedin.com/posts/candidate",
                                "text": "Looking for job as a frontend developer.",
                            },
                        ]
                    },
                    headers={"Authorization": "Bearer secret"},
                )
                return response.status, await response.json()

    status, payload = asyncio.run(run())

    assert status == 200
    assert payload == {"received": 2, "accepted": 1, "published": 1}
    assert len(published_titles) == 1
    assert "Junior Front-End Developer" in published_titles[0]


async def _publish_count(vacancies) -> int:
    return len(vacancies)
