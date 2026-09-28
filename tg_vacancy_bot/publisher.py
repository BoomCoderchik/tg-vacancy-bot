from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramRetryAfter

from .config import Settings
from .description_localization import localize_vacancy_description
from .formatting import format_vacancy_card
from .models import Vacancy
from .storage import VacancyStore

logger = logging.getLogger(__name__)

# How many times a single vacancy card is re-sent after Telegram flood control
# (HTTP 429 / ``TelegramRetryAfter``) before the error is propagated to the caller.
FLOOD_CONTROL_MAX_RETRIES = 3
# Upper bound for a single flood-control wait so a bogus ``retry_after`` cannot
# stall the publishing loop for hours.
FLOOD_CONTROL_MAX_WAIT_SECONDS = 300


async def send_vacancy_card(
    bot: Bot,
    chat_id: int | str,
    text: str,
    *,
    max_retries: int = FLOOD_CONTROL_MAX_RETRIES,
) -> None:
    """Send one vacancy card, retrying after Telegram flood control.

    Telegram answers with ``TelegramRetryAfter`` when the bot posts too fast.
    The helper sleeps for the requested interval (plus a safety second) and
    retries up to ``max_retries`` times. Any other error, and a flood-control
    error that persists after the retries, is raised to the caller so that it
    can decide whether to skip the vacancy or abort.
    """
    attempt = 0
    while True:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            return
        except TelegramRetryAfter as exc:
            attempt += 1
            if attempt > max_retries:
                raise
            retry_after = min(int(getattr(exc, "retry_after", 1) or 1), FLOOD_CONTROL_MAX_WAIT_SECONDS)
            logger.warning(
                "Telegram flood control hit; retrying in %s seconds (attempt %s/%s)",
                retry_after,
                attempt,
                max_retries,
            )
            await asyncio.sleep(retry_after + 1)


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
            await send_vacancy_card(
                self.bot,
                self.settings.target_chat_id,
                format_vacancy_card(public_vacancy),
            )
            if self.store.mark_published(vacancy):
                published += 1
        return published

    async def close(self) -> None:
        await self.bot.session.close()
