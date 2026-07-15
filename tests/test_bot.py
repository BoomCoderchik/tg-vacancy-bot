import asyncio

from tg_vacancy_bot.bot import (
    build_status_text,
    format_whoami_text,
    manual_application_link_text,
    needs_profile_onboarding,
    profile_onboarding_text,
    send_profile_onboarding_reminders,
)
from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import OperatorProfile


def test_build_status_text_does_not_expose_bot_token() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="secret-token",
        TARGET_CHAT_ID="@target",
        ENABLE_ARBEITNOW=False,
        OPERATOR_USER_IDS="",
        LOCALIZE_DESCRIPTIONS="true",
        ENABLE_LINKEDIN_POST_SEARCH=False,
        ENABLE_LINKEDIN_POST_HEADLESS=False,
    )

    text = build_status_text(settings)

    assert "secret-token" not in text
    assert "Target chat: @target" in text
    assert "Forwarded mode: normalize" in text
    assert "Operator allowlist: off" in text
    assert "Description localization: on" in text
    assert "Arbeitnow=off" in text
    assert "WorkingNomads=on" in text
    assert "LinkedInPosts=off" in text
    assert "LinkedInHeadless=off" in text


def test_build_status_text_reports_linkedin_post_search_missing_key() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="secret-token",
        TARGET_CHAT_ID="@target",
        ENABLE_LINKEDIN_POST_SEARCH=True,
        SERPAPI_API_KEY="",
        SERPER_API_KEY="",
        ENABLE_LINKEDIN_POST_HEADLESS=False,
    )

    text = build_status_text(settings)

    assert "LinkedInPosts=missing-key" in text
    assert "LinkedInHeadless=off" in text


def test_build_status_text_reports_linkedin_post_search_on_without_exposing_key() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="secret-token",
        TARGET_CHAT_ID="@target",
        ENABLE_LINKEDIN_POST_SEARCH=True,
        SERPAPI_API_KEY="serp-secret",
        ENABLE_LINKEDIN_POST_HEADLESS=True,
    )

    text = build_status_text(settings)

    assert "LinkedInPosts=on" in text
    assert "LinkedInHeadless=on" in text
    assert "serp-secret" not in text


def test_build_status_text_reports_linkedin_post_search_on_with_serper_key() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="secret-token",
        TARGET_CHAT_ID="@target",
        ENABLE_LINKEDIN_POST_SEARCH=True,
        SERPER_API_KEY="serper-secret",
        ENABLE_LINKEDIN_POST_HEADLESS=False,
    )

    text = build_status_text(settings)

    assert "LinkedInPosts=on" in text
    assert "serper-secret" not in text


def test_format_whoami_text_returns_user_id() -> None:
    assert format_whoami_text(123456) == "Your Telegram user ID: 123456"


def test_format_whoami_text_handles_missing_user() -> None:
    assert "not available" in format_whoami_text(None)


def test_manual_application_link_text_escapes_external_url() -> None:
    text = manual_application_link_text("https://example.com/apply?role=backend&next=1")

    assert "Открыть вакансию" in text
    assert "&amp;" in text


def test_profile_onboarding_text_lists_missing_application_data() -> None:
    text = profile_onboarding_text(None)

    assert "имя и фамилия" in text
    assert "email" in text
    assert "резюме в PDF или DOCX" in text
    assert "Заполнить поля" in text


def test_profile_onboarding_is_not_needed_for_ready_profile() -> None:
    profile = OperatorProfile(
        operator_user_id=42,
        full_name="Ada Lovelace",
        email="ada@example.com",
        resume_stored_name="42-private.pdf",
    )

    assert needs_profile_onboarding(profile) is False


def test_startup_reminder_only_targets_operators_with_incomplete_profiles() -> None:
    class FakeStore:
        def get_operator_profile(self, user_id: int):
            if user_id == 1:
                return None
            return OperatorProfile(
                operator_user_id=user_id,
                full_name="Ada Lovelace",
                email="ada@example.com",
                resume_stored_name="2-private.pdf",
            )

    class FakeBot:
        def __init__(self) -> None:
            self.sent_to: list[int] = []

        async def send_message(self, **kwargs) -> None:
            self.sent_to.append(kwargs["chat_id"])

    settings = Settings(TELEGRAM_BOT_TOKEN="token", TARGET_CHAT_ID="@target", OPERATOR_USER_IDS="1,2")
    bot = FakeBot()

    asyncio.run(send_profile_onboarding_reminders(bot, settings, FakeStore()))

    assert bot.sent_to == [1]
