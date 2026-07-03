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
    def seen(self, vacancy: Vacancy) -> bool:
        return False

    def mark_published(self, vacancy: Vacancy) -> bool:
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
    )
    monkeypatch.setattr("tg_vacancy_bot.source_polling.build_adapters", lambda _: [FakeAdapter()])
    bot = FakeBot()

    published = asyncio.run(poll_sources_once(bot, settings, FakeStore()))

    assert published == 2
    assert len(bot.sent_messages) == 2
