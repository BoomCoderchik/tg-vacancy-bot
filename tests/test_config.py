import pytest
from pydantic import ValidationError

from tg_vacancy_bot.config import Settings


def test_settings_reads_source_poll_interval() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        SOURCE_POLL_INTERVAL_SECONDS="0",
        SOURCE_MAX_PUBLISH_PER_POLL="5",
    )

    assert settings.source_poll_interval_seconds == 0
    assert settings.source_max_publish_per_poll == 5


def test_settings_reads_resume_storage_options() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        RESUME_STORAGE_DIR="private/resumes",
        RESUME_MAX_SIZE_BYTES="2048",
    )

    assert settings.resume_storage_dir == "private/resumes"
    assert settings.resume_max_size_bytes == 2048


def test_settings_validates_application_queue_configuration() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        OPERATOR_USER_IDS="42",
        APPLICATION_ALLOWED_DOMAINS="arbeitnow.com",
        APPLICATION_QUEUE_ENABLED="true",
        APPLICATION_AUTO_SUBMIT="true",
        APPLICATION_QUEUE_PROFILE_FULL_NAME="Ada Lovelace",
        APPLICATION_QUEUE_PROFILE_EMAIL="ada@example.com",
        APPLICATION_QUEUE_RESUME_FILE_ID="telegram-file-id",
        APPLICATION_QUEUE_RESUME_FILE_NAME="resume.pdf",
    )

    settings.require_application_queue()


def test_settings_allows_queue_resume_to_be_registered_through_telegram() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        OPERATOR_USER_IDS="42",
        APPLICATION_ALLOWED_DOMAINS="arbeitnow.com",
        APPLICATION_QUEUE_ENABLED="true",
        APPLICATION_AUTO_SUBMIT="true",
        APPLICATION_QUEUE_PROFILE_FULL_NAME="Ada Lovelace",
        APPLICATION_QUEUE_PROFILE_EMAIL="ada@example.com",
        APPLICATION_QUEUE_RESUME_FILE_ID="",
    )

    settings.require_application_queue()


def test_settings_rejects_long_polling_while_scheduled_application_queue_is_enabled() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        APPLICATION_QUEUE_ENABLED="true",
    )

    with pytest.raises(RuntimeError, match="must not run at the same time"):
        settings.require_bot_polling()


def test_settings_rejects_incomplete_application_queue_configuration() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        APPLICATION_QUEUE_ENABLED="true",
    )

    with pytest.raises(RuntimeError, match="Application queue configuration is incomplete"):
        settings.require_application_queue()


def test_settings_reads_source_max_age_hours() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        SOURCE_MAX_AGE_HOURS="12",
    )

    assert settings.source_max_age_hours == 12


def test_settings_reads_linkedin_post_headless_options() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_LINKEDIN_POST_HEADLESS="true",
        LINKEDIN_POST_HEADLESS_QUERY='site:linkedin.com/posts "ищем" frontend',
        LINKEDIN_POST_HEADLESS_RESULTS_WANTED="7",
        LINKEDIN_POST_HEADLESS_TIMEOUT_SECONDS="25",
    )

    assert settings.enable_linkedin_post_headless is True
    assert settings.linkedin_post_headless_query == 'site:linkedin.com/posts "ищем" frontend'
    assert settings.linkedin_post_headless_results_wanted == 7
    assert settings.linkedin_post_headless_timeout_seconds == 25


def test_settings_reads_linkedin_post_search_options() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_LINKEDIN_POST_SEARCH="true",
        SERPAPI_API_KEY="serp-key",
        SERPER_API_KEY="serper-key",
        LINKEDIN_POST_SEARCH_QUERY='site:linkedin.com/posts "Ищем" frontend',
        LINKEDIN_POST_SEARCH_RESULTS_WANTED="8",
    )

    assert settings.enable_linkedin_post_search is True
    assert settings.serpapi_api_key == "serp-key"
    assert settings.serper_api_key == "serper-key"
    assert settings.linkedin_post_search_query == 'site:linkedin.com/posts "Ищем" frontend'
    assert settings.linkedin_post_search_results_wanted == 8


def test_settings_reads_linkedin_post_scraper_options() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_LINKEDIN_POST_SCRAPER="true",
        LINKEDIN_POST_SCRAPER_QUERY='site:linkedin.com/posts "ищем" frontend',
        LINKEDIN_POST_SCRAPER_SEARCH_PROVIDERS="bing-rss, ddg, bing, unknown, duckduckgo, bing_rss",
        LINKEDIN_POST_SCRAPER_RESULTS_WANTED="8",
    )

    assert settings.enable_linkedin_post_scraper is True
    assert settings.linkedin_post_scraper_query == 'site:linkedin.com/posts "ищем" frontend'
    assert settings.linkedin_post_scraper_search_providers == ("bing_rss", "duckduckgo", "bing")
    assert settings.linkedin_post_scraper_results_wanted == 8


def test_settings_limits_linkedin_post_age_to_five_days() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        LINKEDIN_POST_MAX_AGE_HOURS="120",
    )

    assert settings.linkedin_post_max_age_hours == 120

    with pytest.raises(ValidationError):
        Settings(
            TELEGRAM_BOT_TOKEN="token",
            TARGET_CHAT_ID="@target",
            LINKEDIN_POST_MAX_AGE_HOURS="121",
        )


def test_settings_reads_description_localization_options() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        LOCALIZE_DESCRIPTIONS="true",
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="test-model",
        OPENAI_BASE_URL="https://openrouter.ai/api/v1",
    )

    assert settings.localize_descriptions is True
    assert settings.openai_api_key == "test-key"
    assert settings.openai_model == "test-model"
    assert settings.openai_base_url == "https://openrouter.ai/api/v1"


def test_settings_uses_openrouter_free_fallback_models_by_default() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        OPENAI_BASE_URL="https://openrouter.ai/api/v1",
        OPENAI_FALLBACK_MODELS="",
    )

    assert settings.openai_fallback_models == (
        "qwen/qwen3.6-plus:free",
        "openrouter/free",
        "openai/gpt-4.1-mini",
    )


def test_settings_reads_configured_openai_fallback_models() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        OPENAI_FALLBACK_MODELS="openrouter/free, google/gemma-4-31b-it:free",
        OPENAI_BASE_URL="https://openrouter.ai/api/v1",
    )

    assert settings.openai_fallback_models == (
        "openrouter/free",
        "google/gemma-4-31b-it:free",
        "openai/gpt-4.1-mini",
    )


def test_settings_adds_reliable_openai_translation_fallback() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        OPENAI_BASE_URL="",
        OPENAI_FALLBACK_MODELS="",
    )

    assert settings.openai_fallback_models == ("gpt-4.1-mini",)


def test_settings_uses_groq_free_translation_configuration() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        LOCALIZATION_PROVIDER="groq",
        GROQ_API_KEY="groq-test-key",
    )

    assert settings.localization_api_key == "groq-test-key"
    assert settings.localization_api_key_name == "GROQ_API_KEY"
    assert settings.localization_base_url == "https://api.groq.com/openai/v1"
    assert settings.localization_model == "llama-3.1-8b-instant"
    assert settings.localization_fallback_models == ("openai/gpt-oss-20b",)


def test_settings_allows_overriding_groq_model_chain() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        LOCALIZATION_PROVIDER="groq",
        GROQ_MODEL="preferred-model",
        GROQ_FALLBACK_MODELS="fallback-a, fallback-b, fallback-a",
    )

    assert settings.localization_model == "preferred-model"
    assert settings.localization_fallback_models == ("fallback-a", "fallback-b")
