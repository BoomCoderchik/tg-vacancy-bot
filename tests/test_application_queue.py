import asyncio
from pathlib import Path

from aiogram.types import CallbackQuery, File, Update, User

from tg_vacancy_bot.application_buttons import application_callback_data
from tg_vacancy_bot.application_queue import process_application_queue_once, queue_operator_profile
from tg_vacancy_bot.browser_worker import BrowserInspection
from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.storage import VacancyStore


def queue_settings(tmp_path) -> Settings:
    return Settings(
        TELEGRAM_BOT_TOKEN="123456:test-token",
        TARGET_CHAT_ID="@target",
        OPERATOR_USER_IDS="42",
        DATABASE_PATH=str(tmp_path / "vacancies.sqlite3"),
        APPLICATION_ALLOWED_DOMAINS="arbeitnow.com",
        APPLICATION_QUEUE_ENABLED="true",
        APPLICATION_AUTO_SUBMIT="true",
        APPLICATION_QUEUE_PROFILE_FULL_NAME="Ada Lovelace",
        APPLICATION_QUEUE_PROFILE_EMAIL="ada@example.com",
        APPLICATION_QUEUE_PROFILE_PHONE="+1234567",
        APPLICATION_QUEUE_PROFILE_PERSONAL_URL="https://example.com/ada",
        APPLICATION_QUEUE_PROFILE_COVER_LETTER="Hello",
        APPLICATION_QUEUE_RESUME_FILE_ID="telegram-resume-id",
        APPLICATION_QUEUE_RESUME_FILE_NAME="ada.pdf",
    )


def application_update(update_id: int, vacancy: Vacancy, user_id: int = 42) -> Update:
    return Update(
        update_id=update_id,
        callback_query=CallbackQuery(
            id=f"callback-{update_id}",
            from_user=User(id=user_id, is_bot=False, first_name="Ada"),
            chat_instance="queue-test",
            data=application_callback_data(vacancy),
        ),
    )


class FakeBot:
    def __init__(self, updates) -> None:
        self.updates = list(updates)
        self.messages = []
        self.answers = []
        self.get_updates_calls = []

    async def __call__(self, method):
        self.get_updates_calls.append(method)
        if method.offset is None:
            return self.updates
        return []

    async def answer_callback_query(self, callback_query_id, text):
        self.answers.append((callback_query_id, text))

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)

    async def get_file(self, file_id):
        assert file_id == "telegram-resume-id"
        return File(file_id=file_id, file_unique_id="unique", file_size=6, file_path="documents/resume.pdf")

    async def download_file(self, file_path, destination):
        assert file_path == "documents/resume.pdf"
        Path(destination).write_bytes(b"resume")


class SubmittedWorker:
    def __init__(self) -> None:
        self.calls = []

    async def submit_application(self, vacancy_url, profile, resume_path, before_submit):
        self.calls.append((vacancy_url, profile, Path(resume_path).read_bytes()))
        before_submit()
        return BrowserInspection(status="submitted", title="Success")


def test_queue_processes_callback_downloads_resume_and_submits(tmp_path) -> None:
    settings = queue_settings(tmp_path)
    store = VacancyStore(settings.database_path)
    vacancy = Vacancy(
        title="Python Engineer",
        description="Backend",
        source="Arbeitnow",
        url="https://www.arbeitnow.com/jobs/example",
    )
    store.mark_published(vacancy)
    bot = FakeBot([application_update(1, vacancy)])
    worker = SubmittedWorker()

    result = asyncio.run(
        process_application_queue_once(settings, bot=bot, store=store, browser_worker=worker)
    )

    assert result.submitted == 1
    assert result.applications_processed == 1
    assert worker.calls[0][0] == vacancy.url
    assert worker.calls[0][1].full_name == "Ada Lovelace"
    assert worker.calls[0][2] == b"resume"
    assert bot.messages[0]["chat_id"] == 42
    assert "Отклик отправлен" in bot.messages[0]["text"]
    application, created = store.create_application(42, store.fingerprint(vacancy))
    assert created is False
    assert application.status == "submitted"
    assert bot.get_updates_calls[-1].offset == 2


def test_queue_rejects_unauthorized_callback_without_browser(tmp_path) -> None:
    settings = queue_settings(tmp_path)
    store = VacancyStore(settings.database_path)
    vacancy = Vacancy(
        title="Python Engineer",
        description="Backend",
        source="Arbeitnow",
        url="https://www.arbeitnow.com/jobs/example",
    )
    store.mark_published(vacancy)
    bot = FakeBot([application_update(1, vacancy, user_id=99)])
    worker = SubmittedWorker()

    result = asyncio.run(
        process_application_queue_once(settings, bot=bot, store=store, browser_worker=worker)
    )

    assert result.skipped == 1
    assert worker.calls == []
    assert bot.messages == []


def test_queue_profile_maps_secret_fields_without_storing_resume_bytes(tmp_path) -> None:
    profile = queue_operator_profile(queue_settings(tmp_path), 42)

    assert profile.email == "ada@example.com"
    assert profile.extra_fields == {
        "personal_url": "https://example.com/ada",
        "cover_letter": "Hello",
    }
    assert profile.resume_telegram_file_id == "telegram-resume-id"
    assert profile.resume_stored_name is None


def test_disabled_queue_does_not_fetch_telegram_updates(tmp_path) -> None:
    settings = queue_settings(tmp_path).model_copy(update={"application_queue_enabled": False})
    bot = FakeBot([])

    result = asyncio.run(process_application_queue_once(settings, bot=bot))

    assert result.enabled is False
    assert bot.get_updates_calls == []
