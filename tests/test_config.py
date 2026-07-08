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


def test_settings_reads_source_max_age_hours() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        SOURCE_MAX_AGE_HOURS="12",
    )

    assert settings.source_max_age_hours == 12


def test_settings_reads_jobspy_linkedin_options() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_JOBSPY_LINKEDIN="true",
        JOBSPY_LINKEDIN_QUERY="backend OR frontend",
        JOBSPY_LINKEDIN_LOCATION="Worldwide",
        JOBSPY_LINKEDIN_RESULTS_WANTED="7",
        JOBSPY_LINKEDIN_HOURS_OLD="24",
        JOBSPY_LINKEDIN_FETCH_DESCRIPTION="true",
        JOBSPY_LINKEDIN_PROXIES="http://proxy-a, http://proxy-b",
    )

    assert settings.enable_jobspy_linkedin is True
    assert settings.jobspy_linkedin_query == "backend OR frontend"
    assert settings.jobspy_linkedin_location == "Worldwide"
    assert settings.jobspy_linkedin_results_wanted == 7
    assert settings.jobspy_linkedin_hours_old == 24
    assert settings.jobspy_linkedin_fetch_description is True
    assert settings.jobspy_linkedin_proxies == ("http://proxy-a", "http://proxy-b")


def test_settings_reads_linkedin_post_search_options() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_LINKEDIN_POST_SEARCH="true",
        SERPAPI_API_KEY="serp-key",
        LINKEDIN_POST_SEARCH_QUERY='site:linkedin.com/posts "Ищем" frontend',
        LINKEDIN_POST_SEARCH_LOCATION="Kazakhstan",
        LINKEDIN_POST_SEARCH_RESULTS_WANTED="8",
    )

    assert settings.enable_linkedin_post_search is True
    assert settings.serpapi_api_key == "serp-key"
    assert settings.linkedin_post_search_query == 'site:linkedin.com/posts "Ищем" frontend'
    assert settings.linkedin_post_search_location == "Kazakhstan"
    assert settings.linkedin_post_search_results_wanted == 8


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
