from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from aiogram import Bot
from aiogram.enums import ParseMode

from .application_buttons import application_button
from .config import Settings
from .description_localization import localize_vacancy_description
from .formatting import format_vacancy_card
from .sources import build_adapters, filter_it_vacancies, source_configuration_warnings
from .sources.freshness import filter_fresh_vacancies
from .storage import VacancyStore

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(UTC)


async def poll_sources_once(bot: Bot, settings: Settings, store: VacancyStore) -> int:
    published = 0
    max_publish = settings.source_max_publish_per_poll
    localization_settings = settings.model_copy(update={"localize_descriptions": True})

    for warning in source_configuration_warnings(settings):
        logger.warning(warning)
    for adapter in build_adapters(settings):
        try:
            vacancies = await adapter.fetch()
        except Exception:
            logger.exception("%s: source fetch failed", adapter.name)
            continue

        publishable_vacancies = filter_fresh_vacancies(
            filter_it_vacancies(vacancies),
            max_age_hours=settings.source_max_age_hours,
            current_time=utcnow(),
        )
        for vacancy in publishable_vacancies:
            if max_publish > 0 and published >= max_publish:
                logger.info("Source poll publish limit reached: %s", max_publish)
                return published
            if store.seen(vacancy):
                continue
            try:
                localized_vacancy = await localize_vacancy_description(vacancy, localization_settings)
            except Exception:
                logger.exception(
                    "%s: source description localization failed; publishing the original description",
                    vacancy.source,
                )
                localized_vacancy = vacancy
            await bot.send_message(
                chat_id=settings.target_chat_id,
                text=format_vacancy_card(localized_vacancy),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=application_button(localized_vacancy),
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
