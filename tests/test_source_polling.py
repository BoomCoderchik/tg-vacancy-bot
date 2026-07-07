import asyncio
from datetime import UTC, datetime, timedelta

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.source_polling import poll_sources_once


class FakeBot:
    def __init__(self) -> None:
        self.sent_messages: list[str] = []

    async def send_message(self, **kwargs) -> None:
        self.sent_messages.append(kwargs["text"])


class FakeStore:
    def __init__(self, seen: bool = False) -> None:
        self.seen_result = seen
        self.published: list[Vacancy] = []

    def seen(self, vacancy: Vacancy) -> bool:
        return self.seen_result

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


def test_poll_sources_once_skips_vacancy_when_localization_fails(monkeypatch) -> None:
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

    assert published == 0
    assert bot.sent_messages == []
    assert store.published == []


def test_poll_sources_once_skips_stale_published_vacancies(monkeypatch) -> None:
    now = datetime(2026, 7, 5, 12, tzinfo=UTC)
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        SOURCE_MAX_AGE_HOURS="48",
        LOCALIZE_DESCRIPTIONS="false",
    )

    class StaleAdapter:
        name = "Stale"

        async def fetch(self) -> list[Vacancy]:
            return [
                Vacancy(
                    title="Python Engineer",
                    description="Remote Python role",
                    source="Stale",
                    published_at=now - timedelta(hours=49),
                )
            ]

    monkeypatch.setattr("tg_vacancy_bot.source_polling.build_adapters", lambda _: [StaleAdapter()])
    monkeypatch.setattr("tg_vacancy_bot.source_polling.utcnow", lambda: now)
    bot = FakeBot()

    published = asyncio.run(poll_sources_once(bot, settings, FakeStore()))

    assert published == 0
    assert bot.sent_messages == []


def test_poll_sources_once_publishes_fresh_published_vacancies(monkeypatch) -> None:
    now = datetime(2026, 7, 5, 12, tzinfo=UTC)
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        SOURCE_MAX_AGE_HOURS="48",
        LOCALIZE_DESCRIPTIONS="false",
    )

    class FreshAdapter:
        name = "Fresh"

        async def fetch(self) -> list[Vacancy]:
            return [
                Vacancy(
                    title="Python Engineer",
                    description="Remote Python role",
                    source="Fresh",
                    published_at=now - timedelta(hours=1),
                )
            ]

    monkeypatch.setattr("tg_vacancy_bot.source_polling.build_adapters", lambda _: [FreshAdapter()])
    monkeypatch.setattr("tg_vacancy_bot.source_polling.utcnow", lambda: now)
    bot = FakeBot()

    published = asyncio.run(poll_sources_once(bot, settings, FakeStore()))

    assert published == 1
    assert len(bot.sent_messages) == 1


def test_poll_sources_once_keeps_undated_vacancies(monkeypatch) -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        SOURCE_MAX_AGE_HOURS="48",
        LOCALIZE_DESCRIPTIONS="false",
    )
    monkeypatch.setattr("tg_vacancy_bot.source_polling.build_adapters", lambda _: [FakeAdapter()])
    bot = FakeBot()

    published = asyncio.run(poll_sources_once(bot, settings, FakeStore()))

    assert published == 5
    assert len(bot.sent_messages) == 5


def test_poll_sources_once_keeps_deduplication_before_publish(monkeypatch) -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        SOURCE_MAX_AGE_HOURS="48",
        LOCALIZE_DESCRIPTIONS="false",
    )
    monkeypatch.setattr("tg_vacancy_bot.source_polling.build_adapters", lambda _: [FakeAdapter()])
    bot = FakeBot()

    published = asyncio.run(poll_sources_once(bot, settings, FakeStore(seen=True)))

    assert published == 0
    assert bot.sent_messages == []
