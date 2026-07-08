from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .access_control import parse_operator_user_ids


OPENAI_RELIABLE_TRANSLATION_FALLBACK_MODEL = "gpt-4.1-mini"
OPENROUTER_RELIABLE_TRANSLATION_FALLBACK_MODEL = "openai/gpt-4.1-mini"
OPENROUTER_FREE_FALLBACK_MODELS = ("qwen/qwen3.6-plus:free", "openrouter/free")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    target_chat_id: str = Field(default="", alias="TARGET_CHAT_ID")
    operator_user_ids_raw: str = Field(default="", alias="OPERATOR_USER_IDS")
    forwarded_mode: Literal["normalize", "copy"] = Field(default="normalize", alias="FORWARDED_MODE")
    database_path: str = Field(default="data/vacancies.sqlite3", alias="DATABASE_PATH")
    source_poll_interval_seconds: int = Field(default=900, alias="SOURCE_POLL_INTERVAL_SECONDS")
    source_max_publish_per_poll: int = Field(default=20, alias="SOURCE_MAX_PUBLISH_PER_POLL")
    source_max_age_hours: int = Field(default=48, alias="SOURCE_MAX_AGE_HOURS")
    localize_descriptions: bool = Field(default=False, alias="LOCALIZE_DESCRIPTIONS")

    enable_remotive: bool = Field(default=True, alias="ENABLE_REMOTIVE")
    enable_arbeitnow: bool = Field(default=True, alias="ENABLE_ARBEITNOW")
    enable_remoteok: bool = Field(default=True, alias="ENABLE_REMOTEOK")
    enable_hn_who_is_hiring: bool = Field(default=True, alias="ENABLE_HN_WHO_IS_HIRING")
    enable_jobicy: bool = Field(default=True, alias="ENABLE_JOBICY")
    enable_we_work_remotely: bool = Field(default=True, alias="ENABLE_WE_WORK_REMOTELY")
    enable_himalayas: bool = Field(default=True, alias="ENABLE_HIMALAYAS")
    enable_real_work_from_anywhere: bool = Field(default=True, alias="ENABLE_REAL_WORK_FROM_ANYWHERE")
    enable_jobscollider: bool = Field(default=True, alias="ENABLE_JOBSCOLLIDER")
    enable_linkedin_user_posts: bool = Field(default=False, alias="ENABLE_LINKEDIN_USER_POSTS")
    linkedin_user_posts_feed_url: str = Field(default="", alias="LINKEDIN_USER_POSTS_FEED_URL")
    linkedin_user_posts_webhook_token: str = Field(default="", alias="LINKEDIN_USER_POSTS_WEBHOOK_TOKEN")

    adzuna_app_id: str = Field(default="", alias="ADZUNA_APP_ID")
    adzuna_app_key: str = Field(default="", alias="ADZUNA_APP_KEY")
    adzuna_country: str = Field(default="us", alias="ADZUNA_COUNTRY")
    adzuna_query: str = Field(default="software developer", alias="ADZUNA_QUERY")
    adzuna_location: str = Field(default="", alias="ADZUNA_LOCATION")

    jooble_api_key: str = Field(default="", alias="JOOBLE_API_KEY")
    jooble_keywords: str = Field(default="software developer", alias="JOOBLE_KEYWORDS")
    jooble_location: str = Field(default="", alias="JOOBLE_LOCATION")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")
    openai_fallback_models_raw: str = Field(default="", alias="OPENAI_FALLBACK_MODELS")
    openai_base_url: str = Field(default="", alias="OPENAI_BASE_URL")

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

    def require_runtime(self) -> None:
        missing = []
        if not self.telegram_bot_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.target_chat_id:
            missing.append("TARGET_CHAT_ID")
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(f"Missing required environment variables: {joined}")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def unique_models(models: tuple[str, ...]) -> tuple[str, ...]:
    result = []
    for model in models:
        if model and model not in result:
            result.append(model)
    return tuple(result)
