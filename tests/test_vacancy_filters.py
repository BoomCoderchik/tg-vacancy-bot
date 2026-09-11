import pytest

from tg_vacancy_bot.models import VacancyFilter
from tg_vacancy_bot.sources.filters import (
    DEFAULT_GRADE,
    DEFAULT_SPECIALTY,
    GRADE_LABELS_RU,
    SPECIALTY_LABELS_RU,
    VALID_GRADES,
    VALID_SPECIALTIES,
    evaluate_vacancy_policy,
    filter_it_vacancies,
    normalize_grade,
    normalize_specialty,
)
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.storage import VacancyStore


def test_defaults_preserve_junior_frontend_fullstack() -> None:
    assert DEFAULT_SPECIALTY == "frontend_fullstack"
    assert DEFAULT_GRADE == "junior"
    decision = evaluate_vacancy_policy(
        "We are hiring a Junior Frontend Developer. React."
    )
    assert decision.allowed is True


def test_backend_middle_filter() -> None:
    text = "Ищем Middle Backend разработчика в команду. Python, FastAPI."
    assert evaluate_vacancy_policy(text, "backend", "middle").allowed is True
    # Same text must not pass the default junior frontend filter.
    assert evaluate_vacancy_policy(text).allowed is False


def test_frontend_junior_filter() -> None:
    text = "Ищем Junior Frontend разработчика в команду. React, TypeScript."
    assert evaluate_vacancy_policy(text, "frontend", "junior").allowed is True
    assert evaluate_vacancy_policy(text, "backend", "junior").allowed is False


def test_middle_rejects_senior_but_allows_junior_mix() -> None:
    senior = "We are hiring a Senior Backend Developer. Join our team!"
    assert evaluate_vacancy_policy(senior, "backend", "middle").allowed is False
    assert evaluate_vacancy_policy(senior, "backend", "senior").allowed is True


def test_unknown_values_fall_back_to_defaults() -> None:
    assert normalize_specialty("unknown-spec") == DEFAULT_SPECIALTY
    assert normalize_grade("unknown-grade") == DEFAULT_GRADE
    assert set(VALID_SPECIALTIES) >= {"frontend", "backend", "frontend_fullstack"}
    assert set(VALID_GRADES) >= {"intern", "junior", "middle"}
    assert SPECIALTY_LABELS_RU["backend"] == "Backend"
    assert GRADE_LABELS_RU["junior"] == "Junior"


def test_filter_it_vacancies_uses_specialty_and_grade() -> None:
    vacancies = [
        Vacancy(
            title="Middle Backend Developer",
            description="Ищем Middle Backend разработчика в команду. Python.",
            source="test",
        ),
        Vacancy(
            title="Junior Frontend Developer",
            description="We are hiring a Junior Frontend Developer. React.",
            source="test",
        ),
    ]
    backend_middle = filter_it_vacancies(vacancies, "backend", "middle")
    assert [vacancy.title for vac in backend_middle for vacancy in [vac]] == ["Middle Backend Developer"]


def test_vacancy_filter_storage_roundtrip(tmp_path) -> None:
    store = VacancyStore(str(tmp_path / "vacancies.sqlite3"))
    assert store.get_vacancy_filter() == VacancyFilter(
        specialty="frontend_fullstack", grade="junior"
    )
    saved = store.set_vacancy_filter("backend", "middle")
    assert saved == VacancyFilter(specialty="backend", grade="middle")
    assert store.get_vacancy_filter() == saved


def test_vacancy_filter_storage_rejects_unknown(tmp_path) -> None:
    store = VacancyStore(str(tmp_path / "vacancies.sqlite3"))
    with pytest.raises(ValueError):
        store.set_vacancy_filter("unknown", "junior")
    with pytest.raises(ValueError):
        store.set_vacancy_filter("backend", "unknown")
