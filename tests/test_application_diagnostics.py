import asyncio
from types import SimpleNamespace

from tg_vacancy_bot.application_diagnostics import (
    collect_application_queue_diagnostics,
    format_application_queue_diagnostics,
)
from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import OperatorProfile, Vacancy
from tg_vacancy_bot.storage import VacancyStore


class FakeBot:
    async def get_me(self):
        return SimpleNamespace(id=123456, username="queue_bot")

    async def get_chat(self, chat_id):
        assert chat_id == "@target"
        return SimpleNamespace(title="Vacancy Channel", full_name=None, id=-1001, type="channel")

    async def get_webhook_info(self):
        return SimpleNamespace(url="", pending_update_count=2)


def queue_settings(tmp_path) -> Settings:
    return Settings(
        TELEGRAM_BOT_TOKEN="secret-token",
        TARGET_CHAT_ID="@target",
        OPERATOR_USER_IDS="42",
        DATABASE_PATH=str(tmp_path / "vacancies.sqlite3"),
        APPLICATION_QUEUE_ENABLED="true",
        APPLICATION_AUTO_SUBMIT="true",
        APPLICATION_ALLOWED_DOMAINS="arbeitnow.com",
        APPLICATION_QUEUE_PROFILE_FULL_NAME="Ada Lovelace",
        APPLICATION_QUEUE_PROFILE_EMAIL="ada@example.com",
    )


def test_application_queue_diagnostics_report_safe_runtime_state(tmp_path) -> None:
    settings = queue_settings(tmp_path)
    store = VacancyStore(settings.database_path)
    store.mark_published(
        Vacancy(
            title="Python Engineer",
            description="Backend role",
            source="Arbeitnow",
            url="https://www.arbeitnow.com/jobs/example",
        )
    )
    store.save_operator_profile(
        OperatorProfile(
            operator_user_id=42,
            resume_original_name="private-resume.pdf",
            resume_telegram_file_id="private-file-id",
        )
    )

    result = asyncio.run(
        collect_application_queue_diagnostics(settings, bot=FakeBot(), store=store)
    )
    text = format_application_queue_diagnostics(result)

    assert result.bot_id == 123456
    assert result.pending_update_count == 2
    assert result.published_vacancies == 1
    assert result.applications == 0
    assert result.queue_resume_registered is True
    assert "Bot: @queue_bot (id=123456)" in text
    assert "Pending Telegram updates: 2" in text
    assert "Queue resume registered: yes" in text
    assert "secret-token" not in text
    assert "ada@example.com" not in text
    assert "private-file-id" not in text


def test_application_queue_diagnostics_accept_secret_resume_fallback(tmp_path) -> None:
    settings = queue_settings(tmp_path).model_copy(
        update={"application_queue_resume_file_id": "secret-file-id"}
    )
    store = VacancyStore(settings.database_path)

    result = asyncio.run(
        collect_application_queue_diagnostics(settings, bot=FakeBot(), store=store)
    )

    assert result.queue_resume_registered is True
