import asyncio

import pytest

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.publisher import TelegramPublisher


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


def test_publish_new_raises_localization_error_by_default(monkeypatch) -> None:
    publisher = build_publisher()
    vacancy = Vacancy(title="Python Engineer", description="Remote Python role", source="Fake")

    async def fake_localize(vacancy, settings):
        raise RuntimeError("OpenAI returned an empty localized description.")

    monkeypatch.setattr("tg_vacancy_bot.publisher.localize_vacancy_description", fake_localize)

    with pytest.raises(RuntimeError, match="empty localized description"):
        asyncio.run(publisher.publish_new([vacancy]))


def test_publish_new_can_fallback_to_original_on_localization_error(monkeypatch) -> None:
    publisher = build_publisher()
    vacancy = Vacancy(title="Python Engineer", description="Remote Python role", source="Fake")

    async def fake_localize(vacancy, settings):
        raise RuntimeError("OpenAI returned an empty localized description.")

    monkeypatch.setattr("tg_vacancy_bot.publisher.localize_vacancy_description", fake_localize)

    published = asyncio.run(publisher.publish_new([vacancy], fallback_to_original_on_localization_error=True))

    assert published == 1
    assert "Remote Python role" in publisher.bot.sent_messages[0]
    assert publisher.store.published == [vacancy]
