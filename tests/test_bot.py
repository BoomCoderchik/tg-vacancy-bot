from tg_vacancy_bot.bot import build_status_text
from tg_vacancy_bot.config import Settings


def test_build_status_text_does_not_expose_bot_token() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="secret-token",
        TARGET_CHAT_ID="@target",
        ENABLE_REMOTIVE=True,
        ENABLE_ARBEITNOW=False,
        ADZUNA_APP_ID="app",
        ADZUNA_APP_KEY="key",
    )

    text = build_status_text(settings)

    assert "secret-token" not in text
    assert "Target chat: @target" in text
    assert "Forwarded mode: normalize" in text
    assert "Operator allowlist: off" in text
    assert "Remotive=on" in text
    assert "Arbeitnow=off" in text
    assert "Adzuna=on" in text
