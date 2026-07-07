import asyncio

import pytest

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.description_localization import (
    OpenAIDescriptionLocalizer,
    localize_vacancy_description,
)
from tg_vacancy_bot.models import Vacancy


class FakeResponses:
    def __init__(self) -> None:
        self.request: dict | None = None

    async def create(self, **kwargs):
        self.request = kwargs
        message = type("Message", (), {"content": " Коротко: удаленная backend роль с Python. "})()
        choice = type("Choice", (), {"message": message})()
        return type("Response", (), {"choices": [choice]})()


class FakeChat:
    def __init__(self) -> None:
        self.completions = FakeResponses()


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.chat = FakeChat()


class FailingResponses:
    async def create(self, **kwargs):
        raise RuntimeError("network unavailable")


class FailingChat:
    def __init__(self) -> None:
        self.completions = FailingResponses()


class FailingOpenAIClient:
    def __init__(self) -> None:
        self.chat = FailingChat()


class EmptyThenGoodResponses:
    def __init__(self) -> None:
        self.models: list[str] = []

    async def create(self, **kwargs):
        self.models.append(kwargs["model"])
        content = "" if len(self.models) == 1 else "Короткое русское описание."
        message = type("Message", (), {"content": content})()
        choice = type("Choice", (), {"message": message})()
        return type("Response", (), {"choices": [choice]})()


class EmptyThenGoodChat:
    def __init__(self) -> None:
        self.completions = EmptyThenGoodResponses()


class EmptyThenGoodOpenAIClient:
    def __init__(self) -> None:
        self.chat = EmptyThenGoodChat()


def test_openai_localizer_requests_russian_compressed_description() -> None:
    client = FakeOpenAIClient()
    localizer = OpenAIDescriptionLocalizer(api_key="test-key", model="test-model", client=client)

    text = asyncio.run(localizer.localize("Wir suchen einen Python Entwickler fuer Remote Backend Arbeit."))

    assert text == "Коротко: удаленная backend роль с Python."
    request = client.chat.completions.request
    assert request["model"] == "test-model"
    assert "русский" in request["messages"][0]["content"].lower()
    assert "сожми" in request["messages"][0]["content"].lower()
    assert "не добавляй зарплату" in request["messages"][0]["content"].lower()
    assert "только исходное описание" in request["messages"][0]["content"].lower()
    assert request["messages"][1]["content"] == "Wir suchen einen Python Entwickler fuer Remote Backend Arbeit."
    assert request["max_tokens"] <= 300


def test_openai_localizer_uses_fallback_model_when_primary_returns_empty_text() -> None:
    client = EmptyThenGoodOpenAIClient()
    localizer = OpenAIDescriptionLocalizer(
        api_key="test-key",
        model="bad-free-model",
        fallback_models=("openrouter/free",),
        client=client,
    )

    text = asyncio.run(localizer.localize("Design ecommerce flows."))

    assert text == "Короткое русское описание."
    assert client.chat.completions.models == ["bad-free-model", "openrouter/free"]


def test_openai_localizer_wraps_api_errors() -> None:
    localizer = OpenAIDescriptionLocalizer(
        api_key="test-key",
        model="test-model",
        client=FailingOpenAIClient(),
    )

    with pytest.raises(RuntimeError, match="OpenAI description localization failed"):
        asyncio.run(localizer.localize("Remote backend role."))


class QuotaResponses:
    async def create(self, **kwargs):
        raise RuntimeError("Error code: 429 - {'error': {'code': 'insufficient_quota'}}")


class QuotaChat:
    def __init__(self) -> None:
        self.completions = QuotaResponses()


class QuotaOpenAIClient:
    def __init__(self) -> None:
        self.chat = QuotaChat()


def test_openai_localizer_reports_quota_errors_clearly() -> None:
    localizer = OpenAIDescriptionLocalizer(
        api_key="test-key",
        model="test-model",
        client=QuotaOpenAIClient(),
    )

    with pytest.raises(RuntimeError, match="OpenAI API quota is exhausted"):
        asyncio.run(localizer.localize("Remote backend role."))


def test_localize_vacancy_description_returns_vacancy_with_openai_text() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        LOCALIZE_DESCRIPTIONS="true",
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="test-model",
        OPENAI_BASE_URL="https://openrouter.ai/api/v1",
    )
    vacancy = Vacancy(
        title="Python Engineer",
        description="Long German or English vacancy text.",
        source="RemoteOK",
    )
    localizer = OpenAIDescriptionLocalizer(
        api_key="test-key",
        model="test-model",
        base_url="https://openrouter.ai/api/v1",
        client=FakeOpenAIClient(),
    )

    localized = asyncio.run(localize_vacancy_description(vacancy, settings, localizer=localizer))

    assert localized.description == "Коротко: удаленная backend роль с Python."
    assert localized.title == vacancy.title
    assert localized.source == vacancy.source


def test_localize_vacancy_description_requires_openai_key_when_enabled() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        LOCALIZE_DESCRIPTIONS="true",
        OPENAI_API_KEY="",
    )
    vacancy = Vacancy(title="Python Engineer", description="Remote role.", source="Telegram")

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        asyncio.run(localize_vacancy_description(vacancy, settings))
