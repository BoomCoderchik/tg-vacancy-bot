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


def test_format_vacancy_card_trims_long_description() -> None:
    card = format_vacancy_card(
        Vacancy(
            title="Junior Frontend Developer",
            description="We are hiring. " * 100,
            source="LinkedIn Hiring Posts (Apify)",
        )
    )

    assert "Описание" in card
    lines = card.splitlines()
    description_line = lines[lines.index("<b>Описание</b>") + 1]
    assert len(description_line) <= 310
    assert description_line.endswith("...")
