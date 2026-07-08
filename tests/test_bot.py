from tg_vacancy_bot.bot import build_status_text, format_whoami_text
from tg_vacancy_bot.config import Settings


def test_build_status_text_does_not_expose_bot_token() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="secret-token",
        TARGET_CHAT_ID="@target",
        ENABLE_REMOTIVE=True,
        ENABLE_ARBEITNOW=False,
        OPERATOR_USER_IDS="",
        LOCALIZE_DESCRIPTIONS="true",
        ADZUNA_APP_ID="app",
        ADZUNA_APP_KEY="key",
        ENABLE_LINKEDIN_USER_POSTS=True,
        LINKEDIN_USER_POSTS_FEED_URL="https://authorized.example/linkedin-posts.json",
        LINKEDIN_USER_POSTS_WEBHOOK_TOKEN="webhook-secret",
        LINKEDIN_API_ACCESS_TOKEN="linkedin-token",
        LINKEDIN_API_AUTHOR_URNS="urn:li:person:abc",
    )

    text = build_status_text(settings)

    assert "secret-token" not in text
    assert "Target chat: @target" in text
    assert "Forwarded mode: normalize" in text
    assert "Operator allowlist: off" in text
    assert "Description localization: on" in text
    assert "Remotive=on" in text
    assert "Arbeitnow=off" in text
    assert "Adzuna=on" in text
    assert "LinkedIn user posts=on" in text
    assert "LinkedIn webhook=on" in text
    assert "LinkedIn API=on" in text
    assert "authorized.example" not in text
    assert "webhook-secret" not in text
    assert "linkedin-token" not in text


def test_format_whoami_text_returns_user_id() -> None:
    assert format_whoami_text(123456) == "Your Telegram user ID: 123456"


def test_format_whoami_text_handles_missing_user() -> None:
    assert "not available" in format_whoami_text(None)
