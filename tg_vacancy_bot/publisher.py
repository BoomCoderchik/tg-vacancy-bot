from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from .config import Settings
from .description_localization import localize_vacancy_description
from .formatting import format_vacancy_card
from .models import Vacancy
from .storage import VacancyStore

logger = logging.getLogger(__name__)


class TelegramPublisher:
    def __init__(self, settings: Settings, store: VacancyStore) -> None:
        settings.require_runtime()
        self.settings = settings
        self.store = store
        self.bot = Bot(
            token=settings.telegram_bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )

    async def publish_new(
        self,
        vacancies: list[Vacancy],
        *,
        fallback_to_original_on_localization_error: bool = False,
    ) -> int:
        published = 0
        for vacancy in vacancies:
            if self.store.seen(vacancy):
                continue
            try:
                public_vacancy = await localize_vacancy_description(vacancy, self.settings)
            except Exception as exc:
                if not fallback_to_original_on_localization_error:
                    raise
                logger.warning(
                    "Description localization failed for %r; publishing original description: %s",
                    vacancy.title,
                    exc,
                )
                public_vacancy = vacancy
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
