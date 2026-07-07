from datetime import UTC, datetime

from tg_vacancy_bot.formatting import format_vacancy_card
from tg_vacancy_bot.models import Vacancy


def test_format_vacancy_card_shows_dash_when_stack_is_missing() -> None:
    card = format_vacancy_card(
        Vacancy(
            title="Senior Backend Engineer",
            description="Build APIs.",
            source="Telegram",
        )
    )

    assert "<b>Стек</b>: —" in card


def test_format_vacancy_card_contains_expected_sections() -> None:
    card = format_vacancy_card(
        Vacancy(
            title="Senior Backend Engineer",
            description="Build APIs.",
            source="Telegram",
            url="https://t.me/example/1",
            location="Remote",
            stack=("Python", "FastAPI"),
        )
    )

    assert "IT Job Board" not in card
    assert "💼 <b>Senior Backend Engineer</b>" in card
    assert "📍 <b>Локация</b>: Remote" in card
    assert "🧠 <b>Стек</b>: Python, FastAPI" in card
    assert 'href="https://t.me/example/1"' in card


def test_format_linkedin_user_post_card_contains_role_date_and_post_link() -> None:
    card = format_vacancy_card(
        Vacancy(
            title="Looking for a backend engineer to join our team.",
            description="Looking for a backend engineer to join our team.",
            source="LinkedIn user posts",
            url="https://www.linkedin.com/feed/update/urn:li:activity:123/",
            result_type="linkedin_user_post",
            role="backend engineer",
            detected_at=datetime(2026, 7, 7, 8, tzinfo=UTC),
        )
    )

    assert "IT Job Board" not in card
    assert "LinkedIn-пост с наймом" in card
    assert "backend engineer" in card
    assert "2026-07-07" in card
    assert 'href="https://www.linkedin.com/feed/update/urn:li:activity:123/"' in card
