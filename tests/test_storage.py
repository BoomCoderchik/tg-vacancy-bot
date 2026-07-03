from tg_vacancy_bot.models import Vacancy
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
