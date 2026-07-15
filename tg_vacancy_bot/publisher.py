from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramRetryAfter

from .application_buttons import application_button
from .config import Settings
from .description_localization import localize_vacancy_description
from .formatting import format_vacancy_card
from .models import Vacancy
from .storage import VacancyStore

logger = logging.getLogger(__name__)


class TelegramPublisher:
    def __init__(
        self,
        settings: Settings,
        store: VacancyStore,
        *,
        publish_original_when_localization_fails: bool = False,
    ) -> None:
        settings.require_runtime()
        self.settings = settings
        self.store = store
        self.publish_original_when_localization_fails = publish_original_when_localization_fails
        self.bot = Bot(
            token=settings.telegram_bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )

    async def publish_new(self, vacancies: list[Vacancy]) -> int:
        published = 0
        for vacancy in vacancies:
            if self.store.seen(vacancy):
                continue
            try:
                public_vacancy = await localize_vacancy_description(vacancy, self.settings)
            except Exception as exc:
                logger.warning(
                    "Description localization failed for %r: %s",
                    vacancy.title,
                    exc,
                )
                if not getattr(self, "publish_original_when_localization_fails", False):
                    # Explicit manual publishing must report a broken localization setup.
                    raise
                public_vacancy = vacancy
            try:
                await self.bot.send_message(
                    chat_id=self.settings.target_chat_id,
                    text=format_vacancy_card(public_vacancy),
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=application_button(vacancy),
                )
            except TelegramRetryAfter as exc:
                retry_after = int(getattr(exc, "retry_after", 1))
                logger.warning("Telegram flood control hit; retrying in %s seconds", retry_after)
                await asyncio.sleep(retry_after + 1)
                await self.bot.send_message(
                    chat_id=self.settings.target_chat_id,
                    text=format_vacancy_card(public_vacancy),
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=application_button(vacancy),
                )
            if self.store.mark_published(vacancy):
                published += 1
        return published

    async def close(self) -> None:
        await self.bot.session.close()
