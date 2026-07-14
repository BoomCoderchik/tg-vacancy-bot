from __future__ import annotations

from tg_vacancy_bot.config import Settings

from .adapters.adzuna import AdzunaAdapter
from .adapters.arbeitnow import ArbeitnowAdapter
from .adapters.hacker_news import HackerNewsWhoIsHiringAdapter
from .adapters.himalayas import HimalayasAdapter
from .adapters.jobicy import JobicyAdapter
from .adapters.jobscollider import JobsColliderAdapter
from .adapters.jooble import JoobleAdapter
from .adapters.linkedin_post_headless import LinkedInPostHeadlessAdapter
from .adapters.linkedin_post_scraper import LinkedInPostScraperAdapter
from .adapters.linkedin_post_search import LinkedInPostSearchAdapter, LinkedInPostSerperAdapter
from .adapters.real_work_from_anywhere import RealWorkFromAnywhereAdapter
from .adapters.remoteok import RemoteOkAdapter
from .adapters.remotive import RemotiveAdapter
from .adapters.we_work_remotely import WeWorkRemotelyAdapter
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
    if settings.enable_jobicy:
        adapters.append(JobicyAdapter())
    if settings.enable_we_work_remotely:
        adapters.append(WeWorkRemotelyAdapter())
    if settings.enable_himalayas:
        adapters.append(HimalayasAdapter())
    if settings.enable_real_work_from_anywhere:
        adapters.append(RealWorkFromAnywhereAdapter())
    if settings.enable_jobscollider:
        adapters.append(JobsColliderAdapter())
    if settings.enable_linkedin_post_search and settings.serpapi_api_key:
        adapters.append(LinkedInPostSearchAdapter(settings))
    if settings.enable_linkedin_post_search and settings.serper_api_key:
        adapters.append(LinkedInPostSerperAdapter(settings))
    if settings.enable_linkedin_post_scraper:
        adapters.append(LinkedInPostScraperAdapter(settings))
    if settings.enable_linkedin_post_headless:
        adapters.append(LinkedInPostHeadlessAdapter(settings))
    if settings.adzuna_app_id and settings.adzuna_app_key:
        adapters.append(AdzunaAdapter(settings))
    if settings.jooble_api_key:
        adapters.append(JoobleAdapter(settings))
    return adapters


def source_configuration_warnings(settings: Settings) -> list[str]:
    warnings: list[str] = []
    if settings.enable_linkedin_post_search and not (settings.serpapi_api_key or settings.serper_api_key):
        warnings.append(
            "LinkedIn Hiring Posts source is enabled but SERPAPI_API_KEY or SERPER_API_KEY is missing."
        )
    return warnings
