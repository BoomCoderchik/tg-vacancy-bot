from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.enums import ParseMode

from .config import Settings
from .description_localization import localize_vacancy_description
from .formatting import format_vacancy_card
from .sources import build_adapters, filter_it_vacancies
from .storage import VacancyStore

logger = logging.getLogger(__name__)


async def poll_sources_once(bot: Bot, settings: Settings, store: VacancyStore) -> int:
    published = 0
    max_publish = settings.source_max_publish_per_poll
    for adapter in build_adapters(settings):
        try:
            vacancies = await adapter.fetch()
        except Exception:
            logger.exception("%s: source fetch failed", adapter.name)
            continue

        for vacancy in filter_it_vacancies(vacancies):
            if max_publish > 0 and published >= max_publish:
                logger.info("Source poll publish limit reached: %s", max_publish)
                return published
            if store.seen(vacancy):
                continue
            try:
                public_vacancy = await localize_vacancy_description(vacancy, settings)
            except Exception as exc:
                logger.warning(
                    "%s: description localization failed for %r; publishing original description: %s",
                    adapter.name,
                    vacancy.title,
                    exc,
                )
                public_vacancy = vacancy
            await bot.send_message(
                chat_id=settings.target_chat_id,
                text=format_vacancy_card(public_vacancy),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            if store.mark_published(vacancy):
                published += 1

        logger.info("%s: fetched=%s published_total=%s", adapter.name, len(vacancies), published)

    return published


async def poll_sources_forever(bot: Bot, settings: Settings, store: VacancyStore) -> None:
    interval = settings.source_poll_interval_seconds
    if interval <= 0:
        logger.info("Background source polling is disabled.")
        return

    while True:
        await poll_sources_once(bot, settings, store)
        await asyncio.sleep(interval)
