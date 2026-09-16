from __future__ import annotations

from tg_vacancy_bot.config import Settings

from .adapters.linkedin_post_headless import LinkedInPostHeadlessAdapter
from .adapters.linkedin_post_apify import LinkedInPostApifyAdapter
from .adapters.linkedin_post_guest import LinkedInPostGuestAdapter
from .adapters.linkedin_post_scraper import LinkedInPostScraperAdapter
from .adapters.linkedin_post_search import LinkedInPostSearchAdapter
from .adapters.hh_vacancy_rss import HeadHunterRssAdapter
from .adapters.hh_vacancy_api import HeadHunterApiAdapter
from .adapters.habr_vacancy_api import HabrVacancyApiAdapter
from .adapters.superjob_vacancy_api import SuperJobApiAdapter
from .adapters.trudvsem_vacancy_api import TrudvsemApiAdapter
from .adapters.zp_vacancy_api import ZarplataApiAdapter
from .adapters.russia_vacancy_search import RussiaVacancySearchAdapter
from .adapters.telegram_vacancy_channel import TelegramVacancyChannelAdapter
from .base import SourceAdapter


def build_adapters(settings: Settings) -> list[SourceAdapter]:
    adapters: list[SourceAdapter] = []
    headless_requested = settings.enable_linkedin_post_headless
    headless_registered = (
        headless_requested
        and settings.linkedin_headless_access_authorized
        and bool(settings.linkedin_headless_permission_reference.strip())
    )
    if not headless_requested and settings.enable_linkedin_post_search and settings.serpapi_api_key:
        adapters.append(LinkedInPostSearchAdapter(settings))
    if not headless_requested and settings.enable_linkedin_post_scraper:
        adapters.append(LinkedInPostScraperAdapter(settings))
    if not headless_requested and settings.enable_linkedin_post_apify and settings.apify_api_token:
        adapters.append(LinkedInPostApifyAdapter(settings))
    if headless_registered:
        adapters.append(LinkedInPostHeadlessAdapter(settings))
    # Guest post reading stays independent of the browser-backed headless path
    # and registers whenever enabled: it reads LinkedIn's own public pages
    # through plain HTTP, so no permission boundary applies.
    if settings.enable_linkedin_post_guest:
        adapters.append(LinkedInPostGuestAdapter(settings))
    # Russia-wide sources follow the operator's filter once registered.
    if settings.enable_russia_search:
        adapters.append(RussiaVacancySearchAdapter(settings))
    if settings.enable_russia_telegram:
        adapters.append(TelegramVacancyChannelAdapter(settings))
    # HeadHunter RSS reads the official public feed and needs no key.
    if settings.enable_hhru_rss:
        adapters.append(HeadHunterRssAdapter(settings))
    # HeadHunter JSON API needs a real contact email in the User-Agent header.
    if settings.enable_hh_api and settings.hh_api_contact_email.strip():
        adapters.append(HeadHunterApiAdapter(settings))
    # Habr Career public JSON needs no key; it serves the site's own pages.
    if settings.enable_habr_api:
        adapters.append(HabrVacancyApiAdapter(settings))
    # SuperJob API needs a free registered application key.
    if settings.enable_superjob_api and settings.superjob_api_key.strip():
        adapters.append(SuperJobApiAdapter(settings))
    # Работа России open data needs no key.
    if settings.enable_trudvsem_api:
        adapters.append(TrudvsemApiAdapter(settings))
    # Zarplata.ru public API needs no key; anonymous calls are captcha-limited.
    if settings.enable_zp_api:
        adapters.append(ZarplataApiAdapter(settings))
    return adapters


def source_configuration_warnings(settings: Settings) -> list[str]:
    warnings: list[str] = []
    headless_requested = settings.enable_linkedin_post_headless
    headless_registered = (
        headless_requested
        and settings.linkedin_headless_access_authorized
        and bool(settings.linkedin_headless_permission_reference.strip())
    )
    if (
        not headless_requested
        and settings.enable_linkedin_post_search
        and not settings.serpapi_api_key
    ):
        warnings.append(
            "LinkedIn Hiring Posts source is enabled but SERPAPI_API_KEY is missing."
        )
    if settings.enable_linkedin_post_apify and not settings.apify_api_token:
        warnings.append(
            "LinkedIn Apify source is enabled but APIFY_API_TOKEN is missing."
        )
    if headless_registered and not settings.serpapi_api_key:
        warnings.append(
            "LinkedIn Headless source has no SERPAPI_API_KEY; free Bing/DuckDuckGo discovery is used."
        )
    if settings.enable_linkedin_post_headless and not settings.linkedin_headless_access_authorized:
        warnings.append(
            "LinkedIn Headless source is enabled but LINKEDIN_HEADLESS_ACCESS_AUTHORIZED is false; "
            "direct page reading remains disabled until documented LinkedIn permission or an approved access path exists."
        )
    if (
        settings.enable_linkedin_post_headless
        and settings.linkedin_headless_access_authorized
        and not settings.linkedin_headless_permission_reference.strip()
    ):
        warnings.append(
            "LinkedIn Headless access is marked authorized but LINKEDIN_HEADLESS_PERMISSION_REFERENCE is empty; "
            "direct page reading remains disabled until the approval reference is recorded."
        )
    if settings.enable_russia_telegram and not settings.russia_telegram_channels:
        warnings.append(
            "Russia Telegram Vacancy Channels source is enabled but RUSSIA_TELEGRAM_CHANNELS is empty."
        )
    if settings.enable_hh_api and not settings.hh_api_contact_email.strip():
        warnings.append(
            "HeadHunter API source is enabled but HH_API_CONTACT_EMAIL is empty; "
            "hh.ru requires a real contact email in the User-Agent header."
        )
    if settings.enable_superjob_api and not settings.superjob_api_key.strip():
        warnings.append(
            "SuperJob API source is enabled but SUPERJOB_API_KEY is missing."
        )
    if settings.enable_zp_api:
        warnings.append(
            "Zarplata.ru API source is enabled; anonymous calls are captcha-limited "
            "by the provider and failures are skipped without bypassing protection."
        )
    return warnings