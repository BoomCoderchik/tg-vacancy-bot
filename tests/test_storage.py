import sqlite3

import pytest

from tg_vacancy_bot.models import OperatorProfile, Vacancy
from tg_vacancy_bot.storage import VacancyStore


def test_store_marks_duplicates(tmp_path) -> None:
    store = VacancyStore(str(tmp_path / "vacancies.sqlite3"))
    vacancy = Vacancy(
        title="Python Developer",
        description="Remote backend role",
        source="Test",
        url="https://example.com/job/1",
    )

    assert store.seen(vacancy) is False
    assert store.mark_published(vacancy) is True
    assert store.seen(vacancy) is True
    assert store.mark_published(vacancy) is False


def test_store_deduplicates_linked_vacancies_by_url(tmp_path) -> None:
    store = VacancyStore(str(tmp_path / "vacancies.sqlite3"))
    first = Vacancy(
        title="Looking for a backend engineer",
        description="Looking for a backend engineer to join our team.",
        source="LinkedIn",
        url="https://www.linkedin.com/feed/update/urn:li:activity:123/",
        role="backend engineer",
    )
    duplicate = Vacancy(
        title="Hiring backend engineer",
        description="Hiring backend engineer for our team.",
        source="LinkedIn",
        url="https://www.linkedin.com/feed/update/urn:li:activity:123/",
        role="backend engineer",
    )

    assert store.mark_published(first) is True
    assert store.seen(duplicate) is True
    assert store.mark_published(duplicate) is False


def test_store_migrates_and_persists_operator_profile(tmp_path) -> None:
    database_path = tmp_path / "vacancies.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE published_vacancies (fingerprint TEXT PRIMARY KEY, title TEXT, source TEXT, url TEXT)"
        )
    store = VacancyStore(str(database_path))
    profile = OperatorProfile(
        operator_user_id=42,
        full_name="Ada Lovelace",
        email="ada@example.com",
        desired_salary="100000 USD",
        work_format="remote",
        extra_fields={"notice_period": "2 weeks"},
        resume_original_name="ada-resume.pdf",
        resume_stored_name="42-private.pdf",
    )

    store.save_operator_profile(profile)

    assert store.get_operator_profile(42) == profile
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT version FROM schema_migrations").fetchall() == [(1,)]


def test_store_updates_and_deletes_operator_profile(tmp_path) -> None:
    store = VacancyStore(str(tmp_path / "vacancies.sqlite3"))
    store.save_operator_profile(OperatorProfile(operator_user_id=42, full_name="Ada"))
    store.save_operator_profile(OperatorProfile(operator_user_id=42, full_name="Ada Lovelace"))

    assert store.get_operator_profile(42) == OperatorProfile(operator_user_id=42, full_name="Ada Lovelace")
    assert store.delete_operator_profile(42) is True
    assert store.get_operator_profile(42) is None
    assert store.delete_operator_profile(42) is False


def test_store_rejects_non_string_extra_profile_fields(tmp_path) -> None:
    store = VacancyStore(str(tmp_path / "vacancies.sqlite3"))

    with pytest.raises(ValueError, match="string pairs"):
        store.save_operator_profile(OperatorProfile(operator_user_id=42, extra_fields={"years": 3}))
