import asyncio

import pytest

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.preview import parse_publishable_message, preview_message_card, preview_message_card_async


class FakeLocalizer:
    async def localize(self, description: str) -> str:
        return "Коротко: backend роль с Python."


def test_preview_message_card_formats_vacancy() -> None:
    card = preview_message_card(
        """
Junior Frontend Developer
Location: Remote
Stack: React, TypeScript
Description: Hiring for a junior frontend role.
https://www.linkedin.com/posts/example
"""
    )

    assert "IT Job Board" not in card
    assert "Junior Frontend Developer" in card
    assert "React, TypeScript" in card


def test_preview_message_card_rejects_non_vacancy() -> None:
    with pytest.raises(RuntimeError, match="does not look like an IT vacancy"):
        preview_message_card("hello, this is not useful")


def test_preview_message_card_async_localizes_description() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        LOCALIZE_DESCRIPTIONS="true",
        OPENAI_API_KEY="test-key",
    )

    card = asyncio.run(
        preview_message_card_async(
            """
Junior Frontend Developer
Location: Remote
Stack: React, TypeScript
Description: Hiring for a junior frontend role.
https://www.linkedin.com/posts/example
""",
            settings,
            localizer=FakeLocalizer(),
        )
    )

    assert "Коротко: backend роль с Python." in card
    assert "Hiring for a junior frontend role." not in card


def test_parse_publishable_message_returns_vacancy() -> None:
    vacancy = parse_publishable_message(
        "Hiring Junior Frontend Developer. Stack: React. Remote role."
    )

    assert "Frontend Developer" in vacancy.title
    assert vacancy.source == "Telegram"
    assert "React" in vacancy.stack


def test_parse_publishable_message_treats_linkedin_url_as_regular_vacancy() -> None:
    vacancy = parse_publishable_message(
        "We're hiring a Junior Frontend developer to join our team. "
        "https://www.linkedin.com/feed/update/urn:li:activity:123/"
    )

    assert vacancy.result_type == "vacancy"
    assert vacancy.source == "LinkedIn"
    assert vacancy.url == "https://www.linkedin.com/feed/update/urn:li:activity:123/"
