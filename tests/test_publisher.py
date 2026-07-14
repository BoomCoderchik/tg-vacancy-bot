import asyncio

import pytest
from aiogram.exceptions import TelegramRetryAfter

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.publisher import TelegramPublisher


class FakeBot:
    def __init__(self) -> None:
        self.sent_messages: list[str] = []
        self.reply_markups = []

    async def send_message(self, **kwargs) -> None:
        self.sent_messages.append(kwargs["text"])
        self.reply_markups.append(kwargs.get("reply_markup"))


class FakeStore:
    def __init__(self) -> None:
        self.published: list[Vacancy] = []

    def seen(self, vacancy: Vacancy) -> bool:
        return False

    def mark_published(self, vacancy: Vacancy) -> bool:
        self.published.append(vacancy)
        return True


def build_publisher() -> TelegramPublisher:
    publisher = TelegramPublisher.__new__(TelegramPublisher)
    publisher.settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        LOCALIZE_DESCRIPTIONS="true",
        OPENAI_API_KEY="test-key",
    )
    publisher.store = FakeStore()
    publisher.bot = FakeBot()
    return publisher


def test_publish_new_raises_when_localization_fails(monkeypatch) -> None:
    publisher = build_publisher()
    vacancy = Vacancy(title="Python Engineer", description="Remote Python role", source="Fake")

    async def fake_localize(vacancy, settings):
        raise RuntimeError("OpenAI returned an empty localized description.")

    monkeypatch.setattr("tg_vacancy_bot.publisher.localize_vacancy_description", fake_localize)

    with pytest.raises(RuntimeError, match="empty localized description"):
        asyncio.run(publisher.publish_new([vacancy]))
    assert publisher.bot.sent_messages == []
    assert publisher.store.published == []


def test_publish_new_retries_after_telegram_flood_control(monkeypatch) -> None:
    publisher = build_publisher()
    vacancy = Vacancy(title="Python Engineer", description="Remote Python role", source="Fake")
    sleeps = []

    async def fake_localize(vacancy, settings):
        return vacancy

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    class RetryBot:
        def __init__(self) -> None:
            self.calls = 0

        async def send_message(self, **kwargs) -> None:
            self.calls += 1
            if self.calls == 1:
                raise TelegramRetryAfter(method=object(), message="Too Many Requests", retry_after=2)

    publisher.bot = RetryBot()
    monkeypatch.setattr("tg_vacancy_bot.publisher.localize_vacancy_description", fake_localize)
    monkeypatch.setattr("tg_vacancy_bot.publisher.asyncio.sleep", fake_sleep)

    published = asyncio.run(publisher.publish_new([vacancy]))

    assert published == 1
    assert sleeps == [3]
    assert publisher.bot.calls == 2


def test_publish_new_adds_application_button(monkeypatch) -> None:
    publisher = build_publisher()
    vacancy = Vacancy(title="Python Engineer", description="Remote Python role", source="Fake")

    async def fake_localize(vacancy, settings):
        return vacancy

    monkeypatch.setattr("tg_vacancy_bot.publisher.localize_vacancy_description", fake_localize)

    assert asyncio.run(publisher.publish_new([vacancy])) == 1
    button = publisher.bot.reply_markups[0].inline_keyboard[0][0]
    assert button.text == "Откликнуться"
    assert button.callback_data.startswith("apply:")
