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
