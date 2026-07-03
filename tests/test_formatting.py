from tg_vacancy_bot.formatting import format_vacancy_card
from tg_vacancy_bot.models import Vacancy


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

    assert "<b>IT Job Board</b>" in card
    assert "💼 <b>Senior Backend Engineer</b>" in card
    assert "📍 Локация: Remote" in card
    assert "🧠 Стек: Python, FastAPI" in card
    assert 'href="https://t.me/example/1"' in card
