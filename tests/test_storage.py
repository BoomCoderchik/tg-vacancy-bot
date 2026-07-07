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


def test_store_deduplicates_linkedin_user_posts_by_url(tmp_path) -> None:
    store = VacancyStore(str(tmp_path / "vacancies.sqlite3"))
    first = Vacancy(
        title="Looking for a backend engineer",
        description="Looking for a backend engineer to join our team.",
        source="LinkedIn user posts",
        url="https://www.linkedin.com/feed/update/urn:li:activity:123/",
        result_type="linkedin_user_post",
        role="backend engineer",
    )
    duplicate = Vacancy(
        title="Hiring backend engineer",
        description="Hiring backend engineer for our team.",
        source="LinkedIn user posts",
        url="https://www.linkedin.com/feed/update/urn:li:activity:123/",
        result_type="linkedin_user_post",
        role="backend engineer",
    )

    assert store.mark_published(first) is True
    assert store.seen(duplicate) is True
    assert store.mark_published(duplicate) is False
