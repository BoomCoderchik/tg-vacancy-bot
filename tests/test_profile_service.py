from tg_vacancy_bot.models import OperatorProfile
from tg_vacancy_bot.profile_service import ProfileService
from tg_vacancy_bot.resume_storage import ResumeStorage
from tg_vacancy_bot.storage import VacancyStore


def test_profile_service_replaces_resume_and_preserves_profile_fields(tmp_path) -> None:
    store = VacancyStore(str(tmp_path / "vacancies.sqlite3"))
    storage = ResumeStorage(str(tmp_path / "private-resumes"), max_size_bytes=100)
    service = ProfileService(store, storage)
    store.save_operator_profile(OperatorProfile(operator_user_id=42, full_name="Ada"))

    first = service.save_resume(42, "first.pdf", b"first", telegram_file_id="telegram-first")
    second = service.save_resume(42, "second.docx", b"second", telegram_file_id="telegram-second")

    assert first.full_name == "Ada"
    assert storage.path_for(first.resume_stored_name).exists() is False
    assert storage.path_for(second.resume_stored_name).read_bytes() == b"second"
    assert second.resume_telegram_file_id == "telegram-second"
    assert store.get_operator_profile(42) == second


def test_profile_service_deletes_profile_and_resume(tmp_path) -> None:
    store = VacancyStore(str(tmp_path / "vacancies.sqlite3"))
    storage = ResumeStorage(str(tmp_path / "private-resumes"), max_size_bytes=100)
    service = ProfileService(store, storage)
    profile = service.save_resume(42, "resume.pdf", b"resume")

    assert service.delete_profile(42) is True
    assert store.get_operator_profile(42) is None
    assert storage.path_for(profile.resume_stored_name).exists() is False
    assert service.delete_profile(42) is False
