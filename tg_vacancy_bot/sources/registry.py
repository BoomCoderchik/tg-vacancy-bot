from __future__ import annotations

from tg_vacancy_bot.config import Settings

from .adapters.adzuna import AdzunaAdapter
from .adapters.arbeitnow import ArbeitnowAdapter
from .adapters.hacker_news import HackerNewsWhoIsHiringAdapter
from .adapters.jooble import JoobleAdapter
from .adapters.remoteok import RemoteOkAdapter
from .adapters.remotive import RemotiveAdapter
from .base import SourceAdapter


def build_adapters(settings: Settings) -> list[SourceAdapter]:
    adapters: list[SourceAdapter] = []
    if settings.enable_remotive:
        adapters.append(RemotiveAdapter())
    if settings.enable_arbeitnow:
        adapters.append(ArbeitnowAdapter())
    if settings.enable_remoteok:
        adapters.append(RemoteOkAdapter())
    if settings.enable_hn_who_is_hiring:
        adapters.append(HackerNewsWhoIsHiringAdapter())
    if settings.adzuna_app_id and settings.adzuna_app_key:
        adapters.append(AdzunaAdapter(settings))
    if settings.jooble_api_key:
        adapters.append(JoobleAdapter(settings))
    return adapters
