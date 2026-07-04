from __future__ import annotations

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from .config import Settings
from .description_localization import localize_vacancy_description
from .formatting import format_vacancy_card
from .models import Vacancy
from .storage import VacancyStore


class TelegramPublisher:
    def __init__(self, settings: Settings, store: VacancyStore) -> None:
        settings.require_runtime()
        self.settings = settings
        self.store = store
        self.bot = Bot(
            token=settings.telegram_bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )

    async def publish_new(self, vacancies: list[Vacancy]) -> int:
        published = 0
        for vacancy in vacancies:
            if self.store.seen(vacancy):
                continue
            public_vacancy = await localize_vacancy_description(vacancy, self.settings)
            await self.bot.send_message(
                chat_id=self.settings.target_chat_id,
                text=format_vacancy_card(public_vacancy),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            if self.store.mark_published(vacancy):
                published += 1
        return published

    async def close(self) -> None:
        await self.bot.session.close()
