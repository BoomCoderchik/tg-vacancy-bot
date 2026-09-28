from tg_vacancy_bot.bot import (
    build_status_text,
    format_whoami_text,
)
from tg_vacancy_bot.config import Settings


def test_build_status_text_does_not_expose_bot_token() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="secret-token",
        TARGET_CHAT_ID="@target",
        OPERATOR_USER_IDS="",
        LOCALIZE_DESCRIPTIONS="true",
        ENABLE_LINKEDIN_POST_SEARCH=False,
        ENABLE_LINKEDIN_POST_SCRAPER=False,
        ENABLE_LINKEDIN_POST_HEADLESS=False,
    )

    text = build_status_text(settings)

    assert "secret-token" not in text
    assert "Target chat: @target" in text
    assert "Forwarded mode: normalize" in text
    assert "Operator allowlist: empty (publishing locked)" in text
    assert "Description localization: on" in text
    assert "LinkedInPosts=off" in text
    assert "LinkedInPostScraper=off" in text
    assert "LinkedInHeadless=off" in text


def test_build_status_text_reports_linkedin_post_search_missing_key() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="secret-token",
        TARGET_CHAT_ID="@target",
        ENABLE_LINKEDIN_POST_SEARCH=True,
        SERPAPI_API_KEY="",
        ENABLE_LINKEDIN_POST_HEADLESS=False,
    )

    text = build_status_text(settings)

    assert "LinkedInPosts=missing-key" in text
    assert "LinkedInHeadless=off" in text


def test_build_status_text_reports_linkedin_search_suppressed_by_headless() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="secret-token",
        TARGET_CHAT_ID="@target",
        ENABLE_LINKEDIN_POST_SEARCH=True,
        SERPAPI_API_KEY="serp-secret",
        ENABLE_LINKEDIN_POST_HEADLESS=True,
        LINKEDIN_HEADLESS_ACCESS_AUTHORIZED=True,
        LINKEDIN_HEADLESS_PERMISSION_REFERENCE="linkedin-approval-123",
    )

    text = build_status_text(settings)

    assert "LinkedInPosts=suppressed-by-headless" in text
    assert "LinkedInHeadless=on" in text
    assert "serp-secret" not in text


def test_build_status_text_reports_linkedin_post_search_on_with_serpapi_key() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="secret-token",
        TARGET_CHAT_ID="@target",
        ENABLE_LINKEDIN_POST_SEARCH=True,
        SERPAPI_API_KEY="serp-secret",
        ENABLE_LINKEDIN_POST_HEADLESS=False,
    )

    text = build_status_text(settings)

    assert "LinkedInPosts=on" in text
    assert "serp-secret" not in text


def test_build_status_text_reports_headless_permission_boundary() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="secret-token",
        TARGET_CHAT_ID="@target",
        ENABLE_LINKEDIN_POST_SEARCH=False,
        ENABLE_LINKEDIN_POST_HEADLESS=True,
        LINKEDIN_HEADLESS_ACCESS_AUTHORIZED=False,
    )

    text = build_status_text(settings)

    assert "LinkedInHeadless=permission-required" in text


def test_build_status_text_reports_missing_headless_permission_reference() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="secret-token",
        TARGET_CHAT_ID="@target",
        ENABLE_LINKEDIN_POST_SEARCH=False,
        ENABLE_LINKEDIN_POST_HEADLESS=True,
        LINKEDIN_HEADLESS_ACCESS_AUTHORIZED=True,
        LINKEDIN_HEADLESS_PERMISSION_REFERENCE="",
    )

    text = build_status_text(settings)

    assert "LinkedInHeadless=permission-reference-required" in text


def test_format_whoami_text_returns_user_id() -> None:
    assert format_whoami_text(123456) == "Your Telegram user ID: 123456"


def test_format_whoami_text_handles_missing_user() -> None:
    assert "not available" in format_whoami_text(None)
