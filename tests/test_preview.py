import pytest

from tg_vacancy_bot.preview import parse_publishable_message, preview_message_card


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

    assert "<b>IT Job Board</b>" in card
    assert "Senior Backend Engineer" in card
    assert "Python, FastAPI" in card


def test_preview_message_card_rejects_non_vacancy() -> None:
    with pytest.raises(RuntimeError, match="does not look like an IT vacancy"):
        preview_message_card("hello, this is not useful")


def test_parse_publishable_message_returns_vacancy() -> None:
    vacancy = parse_publishable_message("Hiring Python Engineer. Stack: Python. Remote role.")

    assert "Python Engineer" in vacancy.title
    assert vacancy.source == "Telegram"
    assert "Python" in vacancy.stack
