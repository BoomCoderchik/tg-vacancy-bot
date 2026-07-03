from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .access_control import parse_operator_user_ids


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    target_chat_id: str = Field(default="", alias="TARGET_CHAT_ID")
    operator_user_ids_raw: str = Field(default="", alias="OPERATOR_USER_IDS")
    forwarded_mode: Literal["normalize", "copy"] = Field(default="normalize", alias="FORWARDED_MODE")
    database_path: str = Field(default="data/vacancies.sqlite3", alias="DATABASE_PATH")
    source_poll_interval_seconds: int = Field(default=900, alias="SOURCE_POLL_INTERVAL_SECONDS")
    source_max_publish_per_poll: int = Field(default=20, alias="SOURCE_MAX_PUBLISH_PER_POLL")

    enable_remotive: bool = Field(default=True, alias="ENABLE_REMOTIVE")
    enable_arbeitnow: bool = Field(default=True, alias="ENABLE_ARBEITNOW")
    enable_remoteok: bool = Field(default=True, alias="ENABLE_REMOTEOK")
    enable_hn_who_is_hiring: bool = Field(default=True, alias="ENABLE_HN_WHO_IS_HIRING")

    adzuna_app_id: str = Field(default="", alias="ADZUNA_APP_ID")
    adzuna_app_key: str = Field(default="", alias="ADZUNA_APP_KEY")
    adzuna_country: str = Field(default="us", alias="ADZUNA_COUNTRY")
    adzuna_query: str = Field(default="software developer", alias="ADZUNA_QUERY")
    adzuna_location: str = Field(default="", alias="ADZUNA_LOCATION")

    jooble_api_key: str = Field(default="", alias="JOOBLE_API_KEY")
    jooble_keywords: str = Field(default="software developer", alias="JOOBLE_KEYWORDS")
    jooble_location: str = Field(default="", alias="JOOBLE_LOCATION")

    @property
    def operator_user_ids(self) -> tuple[int, ...]:
        return parse_operator_user_ids(self.operator_user_ids_raw)

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
