from __future__ import annotations

from tg_vacancy_bot.config import Settings

from .adapters.arbeitnow import ArbeitnowAdapter
from .adapters.linkedin_post_headless import LinkedInPostHeadlessAdapter
from .adapters.linkedin_post_scraper import LinkedInPostScraperAdapter
from .adapters.linkedin_post_search import LinkedInPostSearchAdapter, LinkedInPostSerperAdapter
from .adapters.working_nomads import WorkingNomadsAdapter
from .base import SourceAdapter


def build_adapters(settings: Settings) -> list[SourceAdapter]:
    adapters: list[SourceAdapter] = []
    if settings.enable_arbeitnow:
        adapters.append(ArbeitnowAdapter())
    if settings.enable_working_nomads:
        adapters.append(WorkingNomadsAdapter())
    if settings.enable_linkedin_post_search and settings.serpapi_api_key:
        adapters.append(LinkedInPostSearchAdapter(settings))
    if settings.enable_linkedin_post_search and settings.serper_api_key:
        adapters.append(LinkedInPostSerperAdapter(settings))
    if settings.enable_linkedin_post_scraper:
        adapters.append(LinkedInPostScraperAdapter(settings))
    if settings.enable_linkedin_post_headless:
        adapters.append(LinkedInPostHeadlessAdapter(settings))
    return adapters


def source_configuration_warnings(settings: Settings) -> list[str]:
    warnings: list[str] = []
    if settings.enable_linkedin_post_search and not (settings.serpapi_api_key or settings.serper_api_key):
        warnings.append(
            "LinkedIn Hiring Posts source is enabled but SERPAPI_API_KEY or SERPER_API_KEY is missing."
        )
    if settings.enable_linkedin_post_headless and not (settings.serpapi_api_key or settings.serper_api_key):
        warnings.append(
            "LinkedIn Headless source has no SERPAPI_API_KEY or SERPER_API_KEY; Bing discovery is best effort."
        )
    return warnings
