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


def test_web_app_does_not_expose_linkedin_user_posts_endpoint() -> None:
    settings = Settings(TELEGRAM_BOT_TOKEN="token", TARGET_CHAT_ID="@target")

    async def run() -> int:
        app = create_web_app(settings)
        async with TestServer(app) as server:
            async with TestClient(server) as client:
                response = await client.post("/linkedin/user-posts", json={})
                return response.status

    assert asyncio.run(run()) == 404
