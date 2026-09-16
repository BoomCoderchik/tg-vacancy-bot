from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .access_control import parse_operator_user_ids


OPENAI_RELIABLE_TRANSLATION_FALLBACK_MODEL = "gpt-4.1-mini"
OPENROUTER_RELIABLE_TRANSLATION_FALLBACK_MODEL = "openai/gpt-4.1-mini"
OPENROUTER_FREE_FALLBACK_MODELS = (
    "nvidia/nemotron-3-super-120b-a12b:free",
    "openai/gpt-oss-20b:free",
    "openrouter/free",
)
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
# Groq's current flagship production model: the strongest available quality
# for Russian translation and compression, and Groq's own recommended
# replacement for the retired Llama 3.3 70B / Llama 3.1 8B models.
# GPT-OSS models reason before answering; the localization client gives them
# an enlarged completion budget and low reasoning effort (see
# description_localization.py).
GROQ_DEFAULT_TRANSLATION_MODEL = "openai/gpt-oss-120b"
GROQ_DEFAULT_TRANSLATION_FALLBACK_MODELS = ("openai/gpt-oss-20b",)
DEFAULT_LINKEDIN_POST_SCRAPER_QUERY = (
    '(site:linkedin.com/posts OR site:linkedin.com/feed/update) ("we are hiring" OR "we\'re hiring" OR hiring) '
    '("junior frontend developer" OR "junior front-end developer" OR "junior fullstack developer" '
    'OR "junior full-stack developer" OR "intern frontend developer" OR "trainee frontend developer") || '
    '(site:linkedin.com/posts OR site:linkedin.com/feed/update) ("looking for" OR "join our team" OR "open role") '
    '(frontend OR "front-end" OR fullstack OR "full-stack") ("junior" OR intern OR trainee OR "entry level") || '
    '(site:linkedin.com/posts OR site:linkedin.com/feed/update) ("ищем" OR "ищет" OR "нанимаем" OR "в команду") '
    '(фронтенд OR фронтенд-разработчик OR фулстек OR фулстек-разработчик) (джуниор OR стажер OR "без опыта")'
)
# Free public search-result providers used by our own scraper pipeline, in
# reliability order: Bing RSS output first, then DuckDuckGo HTML, Bing HTML,
# the lightweight DuckDuckGo Lite endpoint, and the independent Mojeek index.
DEFAULT_LINKEDIN_POST_SCRAPER_PROVIDERS = (
    "bing_rss,duckduckgo,bing,duckduckgo_lite,mojeek"
)
DEFAULT_LINKEDIN_POST_APIFY_SEARCH_QUERIES = (
    "Hiring junior frontend developer",
    "Hiring junior full stack developer",
    "Looking for junior frontend developer",
    "Ищем джуниор фронтенд разработчика",
    "Ищем джуниор фулстек разработчика",
    "Ищем стажера фронтенд разработчика",
)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    target_chat_id: str = Field(default="", alias="TARGET_CHAT_ID")
    operator_user_ids_raw: str = Field(default="", alias="OPERATOR_USER_IDS")
    forwarded_mode: Literal["normalize", "copy"] = Field(default="normalize", alias="FORWARDED_MODE")
    database_path: str = Field(default="data/vacancies.sqlite3", alias="DATABASE_PATH")
    resume_storage_dir: str = Field(default="data/resumes", alias="RESUME_STORAGE_DIR")
    resume_max_size_bytes: int = Field(default=10 * 1024 * 1024, alias="RESUME_MAX_SIZE_BYTES", gt=0)
    source_poll_interval_seconds: int = Field(default=900, alias="SOURCE_POLL_INTERVAL_SECONDS")
    source_max_publish_per_poll: int = Field(default=20, alias="SOURCE_MAX_PUBLISH_PER_POLL")
    source_max_age_hours: int = Field(default=48, alias="SOURCE_MAX_AGE_HOURS")
    # Scheduled GitHub Actions runs cannot read the local SQLite filter, so the
    # active filter can also be supplied through the environment. When present,
    # these comma-separated values override the stored filter for CLI polling
    # commands and source previews.
    vacancy_filter_specialties_raw: str = Field(default="", alias="VACANCY_FILTER_SPECIALTIES")
    vacancy_filter_grades_raw: str = Field(default="", alias="VACANCY_FILTER_GRADES")
    # Optional auto-sync of the operator-chosen filter to GitHub Actions
    # repository variables. A fine-grained personal access token with the
    # Actions > Variables read/write repository permission is stored only in
    # the local .env and never committed or logged.
    github_filter_sync_token: str = Field(default="", alias="GITHUB_FILTER_SYNC_TOKEN")
    github_repository: str = Field(default="", alias="GITHUB_REPOSITORY")
    localize_descriptions: bool = Field(default=False, alias="LOCALIZE_DESCRIPTIONS")

    enable_linkedin_post_search: bool = Field(default=False, alias="ENABLE_LINKEDIN_POST_SEARCH")
    enable_linkedin_post_scraper: bool = Field(default=False, alias="ENABLE_LINKEDIN_POST_SCRAPER")
    # LinkedIn's public guest post pages: no account, no key, and direct HTTP
    # reading of LinkedIn's own pages that stays independent of keyed search
    # providers once post URLs are discovered.
    enable_linkedin_post_guest: bool = Field(default=False, alias="ENABLE_LINKEDIN_POST_GUEST")
    linkedin_post_guest_query: str = Field(default="", alias="LINKEDIN_POST_GUEST_QUERY")
    linkedin_post_guest_results_wanted: int = Field(
        default=30,
        alias="LINKEDIN_POST_GUEST_RESULTS_WANTED",
        gt=0,
    )
    enable_linkedin_post_apify: bool = Field(default=False, alias="ENABLE_LINKEDIN_POST_APIFY")
    apify_api_token: str = Field(default="", alias="APIFY_API_TOKEN")
    linkedin_post_apify_actor: str = Field(
        default="harvestapi/linkedin-post-search",
        alias="LINKEDIN_POST_APIFY_ACTOR",
    )
    linkedin_post_apify_search_queries_raw: str = Field(
        default="||".join(DEFAULT_LINKEDIN_POST_APIFY_SEARCH_QUERIES),
        alias="LINKEDIN_POST_APIFY_SEARCH_QUERIES",
    )
    linkedin_post_apify_posted_limit: str = Field(
        default="24h",
        alias="LINKEDIN_POST_APIFY_POSTED_LIMIT",
    )
    linkedin_post_apify_max_posts: int = Field(
        default=25,
        alias="LINKEDIN_POST_APIFY_MAX_POSTS",
        gt=0,
    )
    linkedin_post_apify_timeout_seconds: int = Field(
        default=240,
        alias="LINKEDIN_POST_APIFY_TIMEOUT_SECONDS",
        gt=0,
        le=300,
    )
    enable_linkedin_post_headless: bool = Field(default=False, alias="ENABLE_LINKEDIN_POST_HEADLESS")
    linkedin_headless_access_authorized: bool = Field(
        default=False,
        alias="LINKEDIN_HEADLESS_ACCESS_AUTHORIZED",
    )
    linkedin_headless_permission_reference: str = Field(
        default="",
        alias="LINKEDIN_HEADLESS_PERMISSION_REFERENCE",
    )
    # LinkedIn posts must have a verifiable publication date and remain no more
    # than ten days old. A lower value is allowed, but never a longer window.
    linkedin_post_max_age_hours: int = Field(default=240, alias="LINKEDIN_POST_MAX_AGE_HOURS", gt=0, le=240)
    serpapi_api_key: str = Field(default="", alias="SERPAPI_API_KEY")
    linkedin_post_search_query: str = Field(
        default=(
            '(site:linkedin.com/posts OR site:linkedin.com/feed/update) '
            '("we are hiring" OR "we\'re hiring" OR hiring OR "looking for" OR "join our team" OR "open role" OR '
            '"ищем" OR "ищет" OR "нанимаем" OR "в команду") '
            '("junior frontend developer" OR "junior front-end developer" OR "junior frontend engineer" OR '
            '"junior fullstack developer" OR "junior full-stack developer" OR "junior full stack engineer" OR '
            '"intern frontend developer" OR "trainee fullstack developer" OR frontend OR fullstack)'
        ),
        alias="LINKEDIN_POST_SEARCH_QUERY",
    )
    linkedin_post_search_results_wanted: int = Field(default=10, alias="LINKEDIN_POST_SEARCH_RESULTS_WANTED")
    linkedin_post_scraper_query: str = Field(
        default=DEFAULT_LINKEDIN_POST_SCRAPER_QUERY,
        alias="LINKEDIN_POST_SCRAPER_QUERY",
    )
    linkedin_post_scraper_search_providers_raw: str = Field(
        default=DEFAULT_LINKEDIN_POST_SCRAPER_PROVIDERS,
        alias="LINKEDIN_POST_SCRAPER_SEARCH_PROVIDERS",
    )
    # Search depth is intentionally larger than the per-cycle publication
    # budget: deduplication lets later polls publish the remaining fresh posts.
    linkedin_post_scraper_results_wanted: int = Field(default=100, alias="LINKEDIN_POST_SCRAPER_RESULTS_WANTED")
    linkedin_post_headless_query: str = Field(
        default="",
        alias="LINKEDIN_POST_HEADLESS_QUERY",
    )
    linkedin_post_headless_results_wanted: int = Field(default=10, alias="LINKEDIN_POST_HEADLESS_RESULTS_WANTED")
    linkedin_post_search_intents_per_cycle: int = Field(
        default=6,
        alias="LINKEDIN_POST_SEARCH_INTENTS_PER_CYCLE",
        gt=0,
    )
    linkedin_post_headless_timeout_seconds: int = Field(
        default=20,
        alias="LINKEDIN_POST_HEADLESS_TIMEOUT_SECONDS",
        gt=0,
    )
    # Free-discovery depth for the headless adapter: number of Bing result
    # pages per intent before the DuckDuckGo HTML fallback. Higher values read
    # more public search pages; every page still skips protection screens.
    linkedin_headless_discovery_pages: int = Field(
        default=3,
        alias="LINKEDIN_HEADLESS_DISCOVERY_PAGES",
        ge=1,
        le=6,
    )
    # Russia internet-wide vacancy sources: free web search across the whole
    # internet prioritizing Russian job domains, and public Telegram channels.
    enable_russia_search: bool = Field(default=False, alias="ENABLE_RUSSIA_SEARCH")
    russia_search_results_wanted: int = Field(default=50, alias="RUSSIA_SEARCH_RESULTS_WANTED", gt=0)
    russia_search_query: str = Field(default="", alias="RUSSIA_SEARCH_QUERY")
    russia_search_providers_raw: str = Field(
        default=DEFAULT_LINKEDIN_POST_SCRAPER_PROVIDERS,
        alias="RUSSIA_SEARCH_PROVIDERS",
    )
    enable_russia_telegram: bool = Field(default=False, alias="ENABLE_RUSSIA_TELEGRAM")
    russia_telegram_channels_raw: str = Field(default="", alias="RUSSIA_TELEGRAM_CHANNELS")
    russia_telegram_max_posts_per_channel: int = Field(
        default=20,
        alias="RUSSIA_TELEGRAM_MAX_POSTS_PER_CHANNEL",
        gt=0,
    )
    # HeadHunter's official public RSS feed needs no token, account, or API key
    # and returns real Russian-market vacancies that match the operator filter.
    enable_hhru_rss: bool = Field(default=False, alias="ENABLE_HHRU_RSS")
    hhru_rss_query: str = Field(default="", alias="HHRU_RSS_QUERY")
    hhru_rss_results_wanted: int = Field(default=40, alias="HHRU_RSS_RESULTS_WANTED", gt=0)
    # HeadHunter public JSON API: official anonymous vacancy search. hh.ru
    # requires a User-Agent header with a real contact email, so the adapter
    # stays disabled with a warning until HH_API_CONTACT_EMAIL is set.
    enable_hh_api: bool = Field(default=False, alias="ENABLE_HH_API")
    hh_api_contact_email: str = Field(default="", alias="HH_API_CONTACT_EMAIL")
    hh_api_query: str = Field(default="", alias="HH_API_QUERY")
    hh_api_results_wanted: int = Field(default=40, alias="HH_API_RESULTS_WANTED", gt=0)
    # Habr Career public JSON: the same feed the site serves its own vacancy
    # pages, IT-only, no key or account. Carries qualification and salaries.
    enable_habr_api: bool = Field(default=False, alias="ENABLE_HABR_API")
    habr_api_query: str = Field(default="", alias="HABR_API_QUERY")
    habr_api_results_wanted: int = Field(default=40, alias="HABR_API_RESULTS_WANTED", gt=0)
    # SuperJob public API v2: official vacancy search; a free registered
    # application key rides in the X-Api-App-Id header. Vacancy contacts are
    # never requested, so no user authorization is involved.
    enable_superjob_api: bool = Field(default=False, alias="ENABLE_SUPERJOB_API")
    superjob_api_key: str = Field(default="", alias="SUPERJOB_API_KEY")
    superjob_api_query: str = Field(default="", alias="SUPERJOB_API_QUERY")
    superjob_api_results_wanted: int = Field(default=40, alias="SUPERJOB_API_RESULTS_WANTED", gt=0)
    # Работа России open data: the official government JSON vacancy API,
    # no key or account. Contact details from the payload are never mapped.
    enable_trudvsem_api: bool = Field(default=False, alias="ENABLE_TRUDVSEM_API")
    trudvsem_api_query: str = Field(default="", alias="TRUDVSEM_API_QUERY")
    trudvsem_api_results_wanted: int = Field(default=40, alias="TRUDVSEM_API_RESULTS_WANTED", gt=0)
    # Zarplata.ru public API: official vacancy search. Anonymous calls are
    # captcha-limited by the provider, so failures skip quietly with a warning
    # instead of being bypassed.
    enable_zp_api: bool = Field(default=False, alias="ENABLE_ZP_API")
    zp_api_query: str = Field(default="", alias="ZP_API_QUERY")
    zp_api_results_wanted: int = Field(default=40, alias="ZP_API_RESULTS_WANTED", gt=0)
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")
    openai_fallback_models_raw: str = Field(default="", alias="OPENAI_FALLBACK_MODELS")
    openai_base_url: str = Field(default="", alias="OPENAI_BASE_URL")
    localization_provider: Literal["openai", "groq"] = Field(default="openai", alias="LOCALIZATION_PROVIDER")
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(default=GROQ_DEFAULT_TRANSLATION_MODEL, alias="GROQ_MODEL")
    groq_fallback_models_raw: str = Field(default="", alias="GROQ_FALLBACK_MODELS")

    @property
    def operator_user_ids(self) -> tuple[int, ...]:
        return parse_operator_user_ids(self.operator_user_ids_raw)

    @property
    def openai_fallback_models(self) -> tuple[str, ...]:
        configured = tuple(
            model.strip() for model in self.openai_fallback_models_raw.split(",") if model.strip()
        )
        if "openrouter.ai" in self.openai_base_url.lower():
            return unique_models(
                (
                    *(configured or OPENROUTER_FREE_FALLBACK_MODELS),
                    OPENROUTER_RELIABLE_TRANSLATION_FALLBACK_MODEL,
                )
            )
        return unique_models((*configured, OPENAI_RELIABLE_TRANSLATION_FALLBACK_MODEL))

    @property
    def localization_api_key(self) -> str:
        if self.localization_provider == "groq":
            return self.groq_api_key
        return self.openai_api_key

    @property
    def localization_model(self) -> str:
        if self.localization_provider == "groq":
            return self.groq_model
        return self.openai_model

    @property
    def localization_fallback_models(self) -> tuple[str, ...]:
        if self.localization_provider == "groq":
            configured = tuple(
                model.strip() for model in self.groq_fallback_models_raw.split(",") if model.strip()
            )
            return unique_models(configured or GROQ_DEFAULT_TRANSLATION_FALLBACK_MODELS)
        return self.openai_fallback_models

    @property
    def localization_base_url(self) -> str:
        if self.localization_provider == "groq":
            return GROQ_BASE_URL
        return self.openai_base_url

    @property
    def localization_api_key_name(self) -> str:
        if self.localization_provider == "groq":
            return "GROQ_API_KEY"
        return "OPENAI_API_KEY"

    @property
    def linkedin_post_scraper_search_providers(self) -> tuple[str, ...]:
        aliases = {
            "bing-rss": "bing_rss",
            "bingrss": "bing_rss",
            "bing_rss": "bing_rss",
            "ddg": "duckduckgo",
            "duck": "duckduckgo",
            "duckduckgo": "duckduckgo",
            "bing": "bing",
            "ddg-lite": "duckduckgo_lite",
            "ddg_lite": "duckduckgo_lite",
            "duckduckgo-lite": "duckduckgo_lite",
            "duckduckgo_lite": "duckduckgo_lite",
            "mojeek": "mojeek",
        }
        providers = []
        for raw_provider in self.linkedin_post_scraper_search_providers_raw.split(","):
            provider = aliases.get(raw_provider.strip().lower())
            if provider and provider not in providers:
                providers.append(provider)
        return tuple(providers or tuple(DEFAULT_LINKEDIN_POST_SCRAPER_PROVIDERS.split(",")))

    @property
    def linkedin_post_apify_search_queries(self) -> tuple[str, ...]:
        configured = tuple(
            query.strip()
            for query in self.linkedin_post_apify_search_queries_raw.split("||")
            if query.strip()
        )
        return configured or DEFAULT_LINKEDIN_POST_APIFY_SEARCH_QUERIES

    @property
    def russia_search_providers(self) -> tuple[str, ...]:
        aliases = {
            "bing-rss": "bing_rss",
            "bingrss": "bing_rss",
            "bing_rss": "bing_rss",
            "ddg": "duckduckgo",
            "duck": "duckduckgo",
            "duckduckgo": "duckduckgo",
            "bing": "bing",
            "ddg-lite": "duckduckgo_lite",
            "ddg_lite": "duckduckgo_lite",
            "duckduckgo-lite": "duckduckgo_lite",
            "duckduckgo_lite": "duckduckgo_lite",
            "mojeek": "mojeek",
        }
        providers = []
        for raw_provider in self.russia_search_providers_raw.split(","):
            provider = aliases.get(raw_provider.strip().lower())
            if provider and provider not in providers:
                providers.append(provider)
        return tuple(providers or tuple(DEFAULT_LINKEDIN_POST_SCRAPER_PROVIDERS.split(",")))

    @property
    def russia_telegram_channels(self) -> tuple[str, ...]:
        configured = tuple(
            channel.strip().lstrip("@")
            for channel in self.russia_telegram_channels_raw.split(",")
            if channel.strip()
        )
        return configured or ()

    def require_runtime(self) -> None:
        missing = []
        if not self.telegram_bot_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.target_chat_id:
            missing.append("TARGET_CHAT_ID")
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(f"Missing required environment variables: {joined}")

    def require_bot_polling(self) -> None:
        self.require_runtime()


@lru_cache
def get_settings() -> Settings:
    return Settings()


def unique_models(models: tuple[str, ...]) -> tuple[str, ...]:
    result = []
    for model in models:
        if model and model not in result:
            result.append(model)
    return tuple(result)
