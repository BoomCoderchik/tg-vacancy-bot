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
Senior Backend Engineer
Location: Remote
Stack: Python, FastAPI
Description: Hiring for a backend role.
https://www.linkedin.com/posts/example
"""
    )

    assert "IT Job Board" not in card
    assert "Senior Backend Engineer" in card
    assert "Python, FastAPI" in card


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
Senior Backend Engineer
Location: Remote
Stack: Python, FastAPI
Description: Hiring for a backend role.
https://www.linkedin.com/posts/example
""",
            settings,
            localizer=FakeLocalizer(),
        )
    )

    assert "Коротко: backend роль с Python." in card
    assert "Hiring for a backend role." not in card


def test_parse_publishable_message_returns_vacancy() -> None:
    vacancy = parse_publishable_message("Hiring Python Engineer. Stack: Python. Remote role.")

    assert "Python Engineer" in vacancy.title
    assert vacancy.source == "Telegram"
    assert "Python" in vacancy.stack


def test_parse_publishable_message_returns_linkedin_user_post() -> None:
    vacancy = parse_publishable_message(
        "We're hiring a React developer to join our team. "
        "https://www.linkedin.com/feed/update/urn:li:activity:123/"
    )

    assert vacancy.result_type == "linkedin_user_post"
    assert vacancy.role == "React developer"
    assert vacancy.url == "https://www.linkedin.com/feed/update/urn:li:activity:123/"
