import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy, VacancyFilter
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from tg_vacancy_bot.source_polling import poll_sources_forever, poll_sources_once, resolve_active_filter


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

    def get_vacancy_filter(self) -> VacancyFilter:
        return VacancyFilter(specialties=("frontend_fullstack",), grades=("junior",))


class FakeAdapter:
    name = "LinkedIn Hiring Post Scraper"

    async def fetch(self) -> list[Vacancy]:
        return [
            Vacancy(
                title=f"Junior Frontend Developer {index}",
                description="We are hiring a junior frontend developer. React.",
                source=self.name,
            )
            for index in range(5)
        ]


def test_poll_sources_once_respects_publish_limit(monkeypatch) -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        SOURCE_MAX_PUBLISH_PER_POLL="2",
    )
    monkeypatch.setattr("tg_vacancy_bot.source_polling.build_adapters", lambda _: [FakeAdapter()])

    async def fake_localize(vacancy, settings):
        return vacancy

    monkeypatch.setattr("tg_vacancy_bot.source_polling.localize_vacancy_description", fake_localize)
    bot = FakeBot()

    published = asyncio.run(poll_sources_once(bot, settings, FakeStore()))

    assert published == 2
    assert len(bot.sent_messages) == 2


def test_poll_sources_once_always_localizes_description(monkeypatch) -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        SOURCE_MAX_PUBLISH_PER_POLL="1",
        LOCALIZE_DESCRIPTIONS="false",
        OPENAI_API_KEY="test-key",
    )
    monkeypatch.setattr("tg_vacancy_bot.source_polling.build_adapters", lambda _: [FakeAdapter()])
    localized = []

    async def fake_localize(vacancy, settings):
        localized.append((vacancy, settings.localize_descriptions))
        return Vacancy(
            title=vacancy.title,
            description="Переведённое описание.",
            source=vacancy.source,
        )

    monkeypatch.setattr("tg_vacancy_bot.source_polling.localize_vacancy_description", fake_localize)
    bot = FakeBot()

    published = asyncio.run(poll_sources_once(bot, settings, FakeStore()))

    assert published == 1
    assert localized[0][1] is True
    assert "Переведённое описание." in bot.sent_messages[0]


def test_poll_sources_once_publishes_original_when_localization_fails(monkeypatch) -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        OPENAI_API_KEY="test-key",
    )
    monkeypatch.setattr("tg_vacancy_bot.source_polling.build_adapters", lambda _: [FakeAdapter()])

    async def broken_localize(vacancy, settings):
        if vacancy.title.endswith("0"):
            raise RuntimeError("Translation provider failed")
        return vacancy

    monkeypatch.setattr("tg_vacancy_bot.source_polling.localize_vacancy_description", broken_localize)
    bot = FakeBot()

    published = asyncio.run(poll_sources_once(bot, settings, FakeStore()))

    assert published == 5
    assert len(bot.sent_messages) == 5
    assert "We are hiring a junior frontend developer. React." in bot.sent_messages[0]


def test_poll_sources_once_publishes_original_when_localization_key_is_missing(monkeypatch) -> None:
    settings = Settings(TELEGRAM_BOT_TOKEN="token", TARGET_CHAT_ID="@target").model_copy(
        update={"openai_api_key": ""}
    )
    monkeypatch.setattr("tg_vacancy_bot.source_polling.build_adapters", lambda _: [FakeAdapter()])
    bot = FakeBot()

    published = asyncio.run(poll_sources_once(bot, settings, FakeStore()))

    assert published == 5
    assert "We are hiring a junior frontend developer. React." in bot.sent_messages[0]


def test_poll_sources_once_skips_stale_published_vacancies(monkeypatch) -> None:
    now = datetime(2026, 7, 5, 12, tzinfo=UTC)
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        SOURCE_MAX_AGE_HOURS="48",
    )

    class StaleAdapter:
        name = "LinkedIn Hiring Post Scraper"

        async def fetch(self) -> list[Vacancy]:
            return [
                Vacancy(
                    title="Python Engineer",
                    description="Remote Python role",
                    source=self.name,
                    published_at=now - timedelta(hours=49),
                )
            ]

    monkeypatch.setattr("tg_vacancy_bot.source_polling.build_adapters", lambda _: [StaleAdapter()])
    monkeypatch.setattr("tg_vacancy_bot.source_polling.utcnow", lambda: now)
    bot = FakeBot()

    published = asyncio.run(poll_sources_once(bot, settings, FakeStore()))

    assert published == 0
    assert bot.sent_messages == []


def test_poll_sources_once_keeps_deduplication_before_publish(monkeypatch) -> None:
    settings = Settings(TELEGRAM_BOT_TOKEN="token", TARGET_CHAT_ID="@target")
    monkeypatch.setattr("tg_vacancy_bot.source_polling.build_adapters", lambda _: [FakeAdapter()])
    bot = FakeBot()

    published = asyncio.run(poll_sources_once(bot, settings, FakeStore(seen=True)))

    assert published == 0
    assert bot.sent_messages == []


def test_resolve_active_filter_uses_env_override_when_configured() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        VACANCY_FILTER_SPECIALTIES="backend,mobile",
        VACANCY_FILTER_GRADES="senior,lead",
    )
    result = resolve_active_filter(FakeStore(), settings)
    assert result.specialties == ("backend", "mobile")
    assert result.grades == ("senior", "lead")


def test_resolve_active_filter_drops_invalid_env_values() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        VACANCY_FILTER_SPECIALTIES="backend,whatever",
        VACANCY_FILTER_GRADES="lead,middle,queen",
    )
    result = resolve_active_filter(FakeStore(), settings)
    assert result.specialties == ("backend",)
    assert result.grades == ("lead", "middle")


def test_resolve_active_filter_falls_back_to_store_without_env_override() -> None:
    settings = Settings(TELEGRAM_BOT_TOKEN="token", TARGET_CHAT_ID="@target")
    result = resolve_active_filter(FakeStore(), settings)
    assert result.specialties == ("frontend_fullstack",)
    assert result.grades == ("junior",)


def test_poll_sources_once_retries_after_telegram_flood_control(monkeypatch) -> None:
    settings = Settings(TELEGRAM_BOT_TOKEN="token", TARGET_CHAT_ID="@target", SOURCE_MAX_PUBLISH_PER_POLL="1")
    monkeypatch.setattr("tg_vacancy_bot.source_polling.build_adapters", lambda _: [FakeAdapter()])

    async def fake_localize(vacancy, settings):
        return vacancy

    sleeps: list[float] = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    class FloodControlBot:
        def __init__(self) -> None:
            self.calls = 0

        async def send_message(self, **kwargs) -> None:
            self.calls += 1
            if self.calls == 1:
                raise TelegramRetryAfter(method=object(), message="Too Many Requests", retry_after=4)

    monkeypatch.setattr("tg_vacancy_bot.source_polling.localize_vacancy_description", fake_localize)
    monkeypatch.setattr("tg_vacancy_bot.publisher.asyncio.sleep", fake_sleep)
    bot = FloodControlBot()
    store = FakeStore()

    published = asyncio.run(poll_sources_once(bot, settings, store))

    assert published == 1
    assert bot.calls == 2
    assert sleeps == [5]
    assert len(store.published) == 1


def test_poll_sources_once_continues_after_failed_delivery(monkeypatch) -> None:
    # A Telegram error for one vacancy must neither stop the cycle nor mark the
    # vacancy as published, so the next poll can retry it.
    settings = Settings(TELEGRAM_BOT_TOKEN="token", TARGET_CHAT_ID="@target")
    monkeypatch.setattr("tg_vacancy_bot.source_polling.build_adapters", lambda _: [FakeAdapter()])

    async def fake_localize(vacancy, settings):
        return vacancy

    class FlakyBot:
        def __init__(self) -> None:
            self.sent_messages: list[str] = []

        async def send_message(self, **kwargs) -> None:
            if "Developer 1" in kwargs["text"]:
                raise TelegramForbiddenError(method=object(), message="bot was kicked from the channel")
            self.sent_messages.append(kwargs["text"])

    monkeypatch.setattr("tg_vacancy_bot.source_polling.localize_vacancy_description", fake_localize)
    bot = FlakyBot()
    store = FakeStore()

    published = asyncio.run(poll_sources_once(bot, settings, store))

    assert published == 4
    assert len(bot.sent_messages) == 4
    assert [vacancy.title for vacancy in store.published] == [
        "Junior Frontend Developer 0",
        "Junior Frontend Developer 2",
        "Junior Frontend Developer 3",
        "Junior Frontend Developer 4",
    ]


def test_poll_sources_forever_survives_a_failed_cycle(monkeypatch) -> None:
    settings = Settings(TELEGRAM_BOT_TOKEN="token", TARGET_CHAT_ID="@target", SOURCE_POLL_INTERVAL_SECONDS="30")
    calls: list[int] = []
    sleeps: list[float] = []

    async def flaky_poll(bot, settings, store):
        calls.append(len(calls))
        if len(calls) == 1:
            raise RuntimeError("database is locked")
        if len(calls) == 3:
            raise asyncio.CancelledError()
        return 0

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr("tg_vacancy_bot.source_polling.poll_sources_once", flaky_poll)
    monkeypatch.setattr("tg_vacancy_bot.source_polling.asyncio.sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(poll_sources_forever(FakeBot(), settings, FakeStore()))

    # First cycle crashed -> backoff sleep; second cycle succeeded -> normal interval;
    # third cycle was cancelled -> loop stopped instead of swallowing the cancellation.
    assert calls == [0, 1, 2]
    assert sleeps == [30, 30]
