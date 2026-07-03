from tg_vacancy_bot.config import Settings


def test_settings_reads_source_poll_interval() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        SOURCE_POLL_INTERVAL_SECONDS="0",
    )

    assert settings.source_poll_interval_seconds == 0
