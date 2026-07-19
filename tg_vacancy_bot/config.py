from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .access_control import parse_operator_user_ids


OPENAI_RELIABLE_TRANSLATION_FALLBACK_MODEL = "gpt-4.1-mini"
OPENROUTER_RELIABLE_TRANSLATION_FALLBACK_MODEL = "openai/gpt-4.1-mini"
OPENROUTER_FREE_FALLBACK_MODELS = ("qwen/qwen3.6-plus:free", "openrouter/free")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
# Groq currently gives this model a substantially larger free request allowance
# than the larger models. The replacement is kept in the fallback chain because
# Groq can change model availability without changing our client.
GROQ_FREE_TRANSLATION_MODEL = "llama-3.1-8b-instant"
GROQ_FREE_TRANSLATION_FALLBACK_MODELS = ("openai/gpt-oss-20b",)
DEFAULT_LINKEDIN_POST_SCRAPER_QUERY = (
    '(site:linkedin.com/posts OR site:linkedin.com/feed/update) ("we are hiring" OR "we\'re hiring" OR hiring) '
    '(frontend OR backend OR fullstack OR "software developer" OR "software engineer" OR react OR python) || '
    '(site:linkedin.com/posts OR site:linkedin.com/feed/update) ("looking for" OR "join our team" OR "open role") '
    '(developer OR engineer OR frontend OR backend OR fullstack OR react OR python) || '
    '(site:linkedin.com/posts OR site:linkedin.com/feed/update) ("ищем" OR "ищет" OR "нанимаем" OR "в команду") '
    '(разработчик OR инженер OR frontend OR backend OR fullstack OR react OR python)'
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
    browser_profile_dir: str = Field(default="data/browser-profile", alias="BROWSER_PROFILE_DIR")
    browser_headless: bool = Field(default=True, alias="BROWSER_HEADLESS")
    browser_timeout_seconds: int = Field(default=30, alias="BROWSER_TIMEOUT_SECONDS", gt=0)
    application_allowed_domains_raw: str = Field(default="", alias="APPLICATION_ALLOWED_DOMAINS")
    application_queue_enabled: bool = Field(default=False, alias="APPLICATION_QUEUE_ENABLED")
    application_auto_submit: bool = Field(default=False, alias="APPLICATION_AUTO_SUBMIT")
    application_queue_profile_full_name: str = Field(default="", alias="APPLICATION_QUEUE_PROFILE_FULL_NAME")
    application_queue_profile_email: str = Field(default="", alias="APPLICATION_QUEUE_PROFILE_EMAIL")
    application_queue_profile_phone: str = Field(default="", alias="APPLICATION_QUEUE_PROFILE_PHONE")
    application_queue_profile_personal_url: str = Field(default="", alias="APPLICATION_QUEUE_PROFILE_PERSONAL_URL")
    application_queue_profile_cover_letter: str = Field(default="", alias="APPLICATION_QUEUE_PROFILE_COVER_LETTER")
    application_queue_resume_file_id: str = Field(default="", alias="APPLICATION_QUEUE_RESUME_FILE_ID")
    application_queue_resume_file_name: str = Field(default="resume.pdf", alias="APPLICATION_QUEUE_RESUME_FILE_NAME")
    source_poll_interval_seconds: int = Field(default=900, alias="SOURCE_POLL_INTERVAL_SECONDS")
    source_max_publish_per_poll: int = Field(default=20, alias="SOURCE_MAX_PUBLISH_PER_POLL")
    source_max_age_hours: int = Field(default=48, alias="SOURCE_MAX_AGE_HOURS")
    localize_descriptions: bool = Field(default=False, alias="LOCALIZE_DESCRIPTIONS")

    enable_arbeitnow: bool = Field(default=True, alias="ENABLE_ARBEITNOW")
    enable_working_nomads: bool = Field(default=True, alias="ENABLE_WORKING_NOMADS")
    enable_linkedin_post_search: bool = Field(default=False, alias="ENABLE_LINKEDIN_POST_SEARCH")
    enable_linkedin_post_scraper: bool = Field(default=False, alias="ENABLE_LINKEDIN_POST_SCRAPER")
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
    # than five days old. A lower value is allowed, but never a longer window.
    linkedin_post_max_age_hours: int = Field(default=120, alias="LINKEDIN_POST_MAX_AGE_HOURS", gt=0, le=120)
    serpapi_api_key: str = Field(default="", alias="SERPAPI_API_KEY")
    serper_api_key: str = Field(default="", alias="SERPER_API_KEY")
    linkedin_post_search_query: str = Field(
        default=(
            '(site:linkedin.com/posts OR site:linkedin.com/feed/update) '
            '("we are hiring" OR "we\'re hiring" OR hiring OR "looking for" OR "join our team" OR "open role" OR '
            '"ищем" OR "ищет" OR "нанимаем" OR "в команду") '
            '(frontend OR "front-end" OR backend OR fullstack OR "full-stack" OR "software developer" OR '
            '"software engineer" OR developer OR engineer OR react OR python OR designer OR "AI engineer" OR '
            '"ML engineer" OR "LLM engineer" OR разработчик OR инженер)'
        ),
        alias="LINKEDIN_POST_SEARCH_QUERY",
    )
    linkedin_post_search_results_wanted: int = Field(default=10, alias="LINKEDIN_POST_SEARCH_RESULTS_WANTED")
    linkedin_post_scraper_query: str = Field(
        default=DEFAULT_LINKEDIN_POST_SCRAPER_QUERY,
        alias="LINKEDIN_POST_SCRAPER_QUERY",
    )
    linkedin_post_scraper_search_providers_raw: str = Field(
        default="bing_rss,duckduckgo,bing",
        alias="LINKEDIN_POST_SCRAPER_SEARCH_PROVIDERS",
    )
    # Search depth is intentionally larger than the per-cycle publication
    # budget: deduplication lets later polls publish the remaining fresh posts.
    linkedin_post_scraper_results_wanted: int = Field(default=100, alias="LINKEDIN_POST_SCRAPER_RESULTS_WANTED")
    linkedin_post_headless_query: str = Field(
        default=DEFAULT_LINKEDIN_POST_SCRAPER_QUERY,
        alias="LINKEDIN_POST_HEADLESS_QUERY",
    )
    linkedin_post_headless_results_wanted: int = Field(default=10, alias="LINKEDIN_POST_HEADLESS_RESULTS_WANTED")
    linkedin_post_headless_timeout_seconds: int = Field(
        default=20,
        alias="LINKEDIN_POST_HEADLESS_TIMEOUT_SECONDS",
        gt=0,
    )
    localization_max_per_poll: int = Field(default=12, alias="LOCALIZATION_MAX_PER_POLL")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")
    openai_fallback_models_raw: str = Field(default="", alias="OPENAI_FALLBACK_MODELS")
    openai_base_url: str = Field(default="", alias="OPENAI_BASE_URL")
    localization_provider: Literal["openai", "groq"] = Field(default="openai", alias="LOCALIZATION_PROVIDER")
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(default=GROQ_FREE_TRANSLATION_MODEL, alias="GROQ_MODEL")
    groq_fallback_models_raw: str = Field(default="", alias="GROQ_FALLBACK_MODELS")

    @property
    def operator_user_ids(self) -> tuple[int, ...]:
        return parse_operator_user_ids(self.operator_user_ids_raw)

    @property
    def application_allowed_domains(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(item.strip().lower() for item in self.application_allowed_domains_raw.split(",") if item.strip()))

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
            return unique_models(configured or GROQ_FREE_TRANSLATION_FALLBACK_MODELS)
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
        }
        providers = []
        for raw_provider in self.linkedin_post_scraper_search_providers_raw.split(","):
            provider = aliases.get(raw_provider.strip().lower())
            if provider and provider not in providers:
                providers.append(provider)
        return tuple(providers or ("bing_rss", "duckduckgo", "bing"))

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
        if self.application_queue_enabled:
            raise RuntimeError(
                "Telegram long polling and the scheduled application queue must not run at the same time. "
                "Set APPLICATION_QUEUE_ENABLED=false for run/run-web, or stop the polling bot and keep "
                "the GitHub Actions queue enabled."
            )

    def require_application_queue(self) -> None:
        self.require_runtime()
        missing = []
        if len(self.operator_user_ids) != 1:
            missing.append("exactly one OPERATOR_USER_IDS value")
        if not self.application_auto_submit:
            missing.append("APPLICATION_AUTO_SUBMIT=true")
        if "arbeitnow.com" not in self.application_allowed_domains:
            missing.append("APPLICATION_ALLOWED_DOMAINS=arbeitnow.com")
        if len(self.application_queue_profile_full_name.strip().split()) < 2:
            missing.append("APPLICATION_QUEUE_PROFILE_FULL_NAME")
        if not self.application_queue_profile_email.strip():
            missing.append("APPLICATION_QUEUE_PROFILE_EMAIL")
        resume_name = Path(self.application_queue_resume_file_name).name
        if (
            resume_name != self.application_queue_resume_file_name
            or Path(resume_name).suffix.lower() not in {".pdf", ".docx"}
        ):
            missing.append("APPLICATION_QUEUE_RESUME_FILE_NAME (.pdf or .docx)")
        if self.resume_max_size_bytes > 20 * 1024 * 1024:
            missing.append("RESUME_MAX_SIZE_BYTES no greater than Telegram's 20 MB download limit")
        if missing:
            raise RuntimeError("Application queue configuration is incomplete: " + ", ".join(missing))


@lru_cache
def get_settings() -> Settings:
    return Settings()


def unique_models(models: tuple[str, ...]) -> tuple[str, ...]:
    result = []
    for model in models:
        if model and model not in result:
            result.append(model)
    return tuple(result)
