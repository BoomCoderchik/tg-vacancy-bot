import asyncio

import pytest

from tg_vacancy_bot.deployment import get_port, health


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
