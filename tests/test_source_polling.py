import asyncio

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.source_polling import poll_sources_once


class FakeBot:
    def __init__(self) -> None:
        self.sent_messages: list[str] = []

    async def send_message(self, **kwargs) -> None:
        self.sent_messages.append(kwargs["text"])


class FakeStore:
    def __init__(self) -> None:
        self.published: list[Vacancy] = []

    def seen(self, vacancy: Vacancy) -> bool:
        return False

    def mark_published(self, vacancy: Vacancy) -> bool:
        self.published.append(vacancy)
        return True


class FakeAdapter:
    name = "Fake"

    async def fetch(self) -> list[Vacancy]:
        return [
            Vacancy(title=f"Python Engineer {index}", description="Remote Python role", source="Fake")
            for index in range(5)
        ]


def test_poll_sources_once_respects_publish_limit(monkeypatch) -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        SOURCE_MAX_PUBLISH_PER_POLL="2",
        LOCALIZE_DESCRIPTIONS="false",
    )
    monkeypatch.setattr("tg_vacancy_bot.source_polling.build_adapters", lambda _: [FakeAdapter()])
    bot = FakeBot()

    published = asyncio.run(poll_sources_once(bot, settings, FakeStore()))

    assert published == 2
    assert len(bot.sent_messages) == 2


def test_poll_sources_once_localizes_description_before_sending(monkeypatch) -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        SOURCE_MAX_PUBLISH_PER_POLL="1",
        LOCALIZE_DESCRIPTIONS="true",
        OPENAI_API_KEY="test-key",
    )
    monkeypatch.setattr("tg_vacancy_bot.source_polling.build_adapters", lambda _: [FakeAdapter()])
    bot = FakeBot()
    store = FakeStore()

    async def fake_localize(vacancy, settings):
        return Vacancy(
            title=vacancy.title,
            description="Коротко: удаленная Python роль.",
            source=vacancy.source,
        )

    monkeypatch.setattr("tg_vacancy_bot.source_polling.localize_vacancy_description", fake_localize)

    published = asyncio.run(poll_sources_once(bot, settings, store))

    assert published == 1
    assert "Коротко: удаленная Python роль." in bot.sent_messages[0]
    assert store.published[0].description == "Remote Python role"


def test_poll_sources_once_publishes_original_when_localization_fails(monkeypatch) -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        SOURCE_MAX_PUBLISH_PER_POLL="1",
        LOCALIZE_DESCRIPTIONS="true",
        OPENAI_API_KEY="test-key",
    )
    monkeypatch.setattr("tg_vacancy_bot.source_polling.build_adapters", lambda _: [FakeAdapter()])
    bot = FakeBot()
    store = FakeStore()

    async def fake_localize(vacancy, settings):
        raise RuntimeError("OpenAI returned an empty localized description.")

    monkeypatch.setattr("tg_vacancy_bot.source_polling.localize_vacancy_description", fake_localize)

    published = asyncio.run(poll_sources_once(bot, settings, store))

    assert published == 1
    assert "Remote Python role" in bot.sent_messages[0]
    assert store.published[0].description == "Remote Python role"
