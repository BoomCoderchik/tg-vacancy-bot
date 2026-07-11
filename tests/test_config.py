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


def test_settings_reads_linkedin_post_scraper_options() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_LINKEDIN_POST_SCRAPER="true",
        LINKEDIN_POST_SCRAPER_QUERY='site:linkedin.com/posts "ищем" frontend',
        LINKEDIN_POST_SCRAPER_LOCATION="Kazakhstan",
        LINKEDIN_POST_SCRAPER_RESULTS_WANTED="8",
    )

    assert settings.enable_linkedin_post_scraper is True
    assert settings.linkedin_post_scraper_query == 'site:linkedin.com/posts "ищем" frontend'
    assert settings.linkedin_post_scraper_location == "Kazakhstan"
    assert settings.linkedin_post_scraper_results_wanted == 8


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
