import pytest
import logging

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

        async def publish_new(self, vacancies):
            published_batches.append(list(vacancies))
            return len(vacancies)

        async def close(self) -> None:
            pass

    monkeypatch.setattr("tg_vacancy_bot.app.get_settings", lambda: settings)
    monkeypatch.setattr("tg_vacancy_bot.app.build_adapters", lambda _: [FakeAdapter()])
    monkeypatch.setattr("tg_vacancy_bot.app.TelegramPublisher", FakePublisher)

    import asyncio

    asyncio.run(poll_once())

    assert [len(batch) for batch in published_batches] == [1, 1]


def test_poll_once_skips_vacancy_when_localization_fails(monkeypatch, tmp_path) -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        DATABASE_PATH=str(tmp_path / "vacancies.sqlite3"),
        SOURCE_MAX_PUBLISH_PER_POLL="2",
        LOCALIZE_DESCRIPTIONS="true",
        OPENAI_API_KEY="test-key",
    )
    attempted = []

    class FakeAdapter:
        name = "Fake"

        async def fetch(self):
            return [
                Vacancy(title="UI/UX Designer", description="Design ecommerce flows.", source="Fake"),
                Vacancy(title="Python Engineer", description="Remote Python role", source="Fake"),
            ]

    class FakePublisher:
        def __init__(self, settings, store) -> None:
            pass

        async def publish_new(self, vacancies):
            attempted.extend(vacancies)
            if vacancies[0].title == "UI/UX Designer":
                raise RuntimeError("OpenAI returned an empty localized description.")
            return len(vacancies)

        async def close(self) -> None:
            pass

    monkeypatch.setattr("tg_vacancy_bot.app.get_settings", lambda: settings)
    monkeypatch.setattr("tg_vacancy_bot.app.build_adapters", lambda _: [FakeAdapter()])
    monkeypatch.setattr("tg_vacancy_bot.app.TelegramPublisher", FakePublisher)

    import asyncio

    asyncio.run(poll_once())

    assert [vacancy.title for vacancy in attempted] == ["UI/UX Designer", "Python Engineer"]


def test_poll_once_warns_when_linkedin_posts_enabled_without_serpapi_key(
    caplog,
    monkeypatch,
    tmp_path,
) -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        DATABASE_PATH=str(tmp_path / "vacancies.sqlite3"),
        ENABLE_REMOTIVE=False,
        ENABLE_ARBEITNOW=False,
        ENABLE_REMOTEOK=False,
        ENABLE_HN_WHO_IS_HIRING=False,
        ENABLE_JOBICY=False,
        ENABLE_WE_WORK_REMOTELY=False,
        ENABLE_HIMALAYAS=False,
        ENABLE_REAL_WORK_FROM_ANYWHERE=False,
        ENABLE_JOBSCOLLIDER=False,
        ENABLE_LINKEDIN_POST_SEARCH=True,
        SERPAPI_API_KEY="",
    )

    class FakePublisher:
        def __init__(self, settings, store) -> None:
            pass

        async def publish_new(self, vacancies):
            return len(vacancies)

        async def close(self) -> None:
            pass

    monkeypatch.setattr("tg_vacancy_bot.app.get_settings", lambda: settings)
    monkeypatch.setattr("tg_vacancy_bot.app.TelegramPublisher", FakePublisher)

    import asyncio

    with caplog.at_level(logging.WARNING):
        asyncio.run(poll_once())

    assert "LinkedIn Hiring Posts source is enabled but SERPAPI_API_KEY is missing." in caplog.text
