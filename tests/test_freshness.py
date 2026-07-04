from datetime import UTC, datetime, timedelta

from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.sources.freshness import filter_fresh_vacancies


def test_filter_fresh_vacancies_rejects_vacancies_older_than_max_age() -> None:
    now = datetime(2026, 7, 5, 12, tzinfo=UTC)
    vacancies = [
        Vacancy(
            title="Old Python Engineer",
            description="Remote Python role",
            source="Test",
            published_at=now - timedelta(hours=49),
        )
    ]

    assert filter_fresh_vacancies(vacancies, max_age_hours=48, current_time=now) == []


def test_filter_fresh_vacancies_keeps_fresh_vacancies() -> None:
    now = datetime(2026, 7, 5, 12, tzinfo=UTC)
    vacancy = Vacancy(
        title="Fresh Python Engineer",
        description="Remote Python role",
        source="Test",
        published_at=now - timedelta(hours=2),
    )

    assert filter_fresh_vacancies([vacancy], max_age_hours=48, current_time=now) == [vacancy]


def test_filter_fresh_vacancies_keeps_vacancies_without_publication_date() -> None:
    now = datetime(2026, 7, 5, 12, tzinfo=UTC)
    vacancy = Vacancy(title="Python Engineer", description="Remote Python role", source="Test")

    assert filter_fresh_vacancies([vacancy], max_age_hours=48, current_time=now) == [vacancy]
