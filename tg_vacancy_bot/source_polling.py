from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from aiogram import Bot

from .config import Settings
from .description_localization import localize_vacancy_description
from .formatting import format_vacancy_card
from .models import VacancyFilter
from .publisher import send_vacancy_card
from .sources import build_adapters, filter_it_vacancies, source_configuration_warnings
from .sources.filter_queries import apply_filter_queries
from .sources.filters import normalize_grades, normalize_specialties
from .sources.freshness import filter_fresh_vacancies
from .storage import VacancyStore

logger = logging.getLogger(__name__)

# Pause before the next polling cycle when a whole cycle crashed, so a broken
# dependency (Telegram outage, database error) does not turn into a hot loop.
POLL_ERROR_BACKOFF_SECONDS = 60


def utcnow() -> datetime:
    return datetime.now(UTC)


def filter_from_environment(settings: Settings | None) -> VacancyFilter | None:
    """Build the filter from VACANCY_FILTER_* env vars, or None when unset."""
    if settings is None:
        return None
    if not settings.vacancy_filter_specialties_raw and not settings.vacancy_filter_grades_raw:
        return None
    specialties = [item.strip() for item in settings.vacancy_filter_specialties_raw.split(",") if item.strip()]
    grades = [item.strip() for item in settings.vacancy_filter_grades_raw.split(",") if item.strip()]
    return VacancyFilter(
        specialties=tuple(normalize_specialties(specialties or None)),
        grades=tuple(normalize_grades(grades or None)),
    )


def resolve_active_filter(store: VacancyStore, settings: Settings | None = None) -> VacancyFilter:
    """Return the stored global filter, falling back to defaults for legacy stores."""
    env_filter = filter_from_environment(settings)
    if env_filter is not None:
        return env_filter
    getter = getattr(store, "get_vacancy_filter", None)
    if callable(getter):
        try:
            return getter()
        except Exception:
            logger.warning("Could not read stored vacancy filter; using defaults.", exc_info=True)
    return VacancyFilter()


async def poll_sources_once(bot: Bot, settings: Settings, store: VacancyStore) -> int:
    active_filter = resolve_active_filter(store, settings)
    settings = apply_filter_queries(settings, active_filter.specialties, active_filter.grades)
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
            filter_it_vacancies(vacancies, active_filter.specialties, active_filter.grades),
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
            # A single failed delivery (Telegram error after flood-control retries,
            # formatting problem, storage error) must not abort the whole cycle:
            # log it, leave the vacancy unpublished so the next poll retries it,
            # and continue with the remaining vacancies.
            try:
                await send_vacancy_card(
                    bot,
                    settings.target_chat_id,
                    format_vacancy_card(localized_vacancy),
                )
                if store.mark_published(vacancy):
                    published += 1
            except Exception:
                logger.exception("%s: failed to publish %r", vacancy.source, vacancy.title)
                continue

        logger.info("%s: fetched=%s published_total=%s", adapter.name, len(vacancies), published)

    return published


async def poll_sources_forever(bot: Bot, settings: Settings, store: VacancyStore) -> None:
    interval = settings.source_poll_interval_seconds
    if interval <= 0:
        logger.info("Background source polling is disabled.")
        return

    while True:
        try:
            await poll_sources_once(bot, settings, store)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Never let one broken cycle kill the background task: the bot would
            # keep answering commands while silently publishing nothing.
            logger.exception("Background source polling cycle failed; retrying after backoff")
            await asyncio.sleep(min(interval, POLL_ERROR_BACKOFF_SECONDS))
            continue
        await asyncio.sleep(interval)
