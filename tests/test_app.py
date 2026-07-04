import pytest

from tg_vacancy_bot.app import main, poll_once
from tg_vacancy_bot.config import Settings, get_settings
from tg_vacancy_bot.models import Vacancy


def test_main_reports_missing_runtime_config(capsys, monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TARGET_CHAT_ID", raising=False)
    get_settings.cache_clear()

    with pytest.raises(SystemExit) as exc:
        main(["run"])

    assert exc.value.code == 2
    assert "Missing required environment variables" in capsys.readouterr().err
    get_settings.cache_clear()


def test_poll_once_respects_global_publish_limit(monkeypatch, tmp_path) -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        DATABASE_PATH=str(tmp_path / "vacancies.sqlite3"),
        SOURCE_MAX_PUBLISH_PER_POLL="2",
        LOCALIZE_DESCRIPTIONS="false",
    )
    published_batches = []

    class FakeAdapter:
        name = "Fake"

        async def fetch(self):
            return [
                Vacancy(title=f"Python Engineer {index}", description="Remote Python role", source="Fake")
                for index in range(5)
            ]

    class FakePublisher:
        def __init__(self, settings, store) -> None:
            pass

        async def publish_new(self, vacancies, *, fallback_to_original_on_localization_error=False):
            published_batches.append(list(vacancies))
            return len(vacancies)

        async def close(self) -> None:
            pass

    monkeypatch.setattr("tg_vacancy_bot.app.get_settings", lambda: settings)
    monkeypatch.setattr("tg_vacancy_bot.app.build_adapters", lambda _: [FakeAdapter()])
    monkeypatch.setattr("tg_vacancy_bot.app.TelegramPublisher", FakePublisher)

    import asyncio

    asyncio.run(poll_once())

    assert [len(batch) for batch in published_batches] == [2]
