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
        ENABLE_LINKEDIN_POST_SEARCH=False,
        ENABLE_JOBSPY_LINKEDIN=False,
        ADZUNA_APP_ID="app",
        ADZUNA_APP_KEY="key",
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
    assert "LinkedInPosts=off" in text
    assert "JobSpyLinkedIn=off" in text


def test_build_status_text_reports_linkedin_post_search_missing_key() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="secret-token",
        TARGET_CHAT_ID="@target",
        ENABLE_LINKEDIN_POST_SEARCH=True,
        SERPAPI_API_KEY="",
        ENABLE_JOBSPY_LINKEDIN=False,
    )

    text = build_status_text(settings)

    assert "LinkedInPosts=missing-key" in text
    assert "JobSpyLinkedIn=off" in text


def test_build_status_text_reports_linkedin_post_search_on_without_exposing_key() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="secret-token",
        TARGET_CHAT_ID="@target",
        ENABLE_LINKEDIN_POST_SEARCH=True,
        SERPAPI_API_KEY="serp-secret",
        ENABLE_JOBSPY_LINKEDIN=True,
    )

    text = build_status_text(settings)

    assert "LinkedInPosts=on" in text
    assert "JobSpyLinkedIn=on" in text
    assert "serp-secret" not in text


def test_format_whoami_text_returns_user_id() -> None:
    assert format_whoami_text(123456) == "Your Telegram user ID: 123456"


def test_format_whoami_text_handles_missing_user() -> None:
    assert "not available" in format_whoami_text(None)
