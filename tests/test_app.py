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


def test_check_sources_reports_missing_linkedin_post_search_key(capsys, monkeypatch) -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_REMOTIVE=False,
        ENABLE_ARBEITNOW=False,
        ENABLE_REMOTEOK=False,
        ENABLE_HN_WHO_IS_HIRING=False,
        ENABLE_JOBICY=False,
        ENABLE_WE_WORK_REMOTELY=False,
        ENABLE_HIMALAYAS=False,
        ENABLE_REAL_WORK_FROM_ANYWHERE=False,
        ENABLE_JOBSCOLLIDER=False,
        ENABLE_JOBSPY_LINKEDIN=False,
        ENABLE_LINKEDIN_POST_SEARCH=True,
        ENABLE_LINKEDIN_POST_SCRAPER=False,
        SERPAPI_API_KEY="",
    )
    monkeypatch.setattr("tg_vacancy_bot.app.get_settings", lambda: settings)

    main(["check-sources"])

    output = capsys.readouterr().out
    assert "Source configuration" in output
    assert "Warnings:\n" in output
    assert "WARNING: LinkedIn Hiring Posts source is enabled but SERPAPI_API_KEY is missing." in output
    assert "Registered adapters: none" in output


def test_check_sources_reports_registered_linkedin_post_search_without_exposing_key(
    capsys,
    monkeypatch,
) -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_REMOTIVE=False,
        ENABLE_ARBEITNOW=False,
        ENABLE_REMOTEOK=False,
        ENABLE_HN_WHO_IS_HIRING=False,
        ENABLE_JOBICY=False,
        ENABLE_WE_WORK_REMOTELY=False,
        ENABLE_HIMALAYAS=False,
        ENABLE_REAL_WORK_FROM_ANYWHERE=False,
        ENABLE_JOBSCOLLIDER=False,
        ENABLE_JOBSPY_LINKEDIN=False,
        ENABLE_LINKEDIN_POST_SEARCH=True,
        SERPAPI_API_KEY="serp-secret",
    )
    monkeypatch.setattr("tg_vacancy_bot.app.get_settings", lambda: settings)

    main(["check-sources"])

    output = capsys.readouterr().out
    assert "Warnings: none" in output
    assert "Registered adapters: LinkedIn Hiring Posts" in output
    assert "serp-secret" not in output


def test_preview_sources_prints_filtered_candidates_without_publishing(capsys, monkeypatch) -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_REMOTIVE=False,
        ENABLE_ARBEITNOW=False,
        ENABLE_REMOTEOK=False,
        ENABLE_HN_WHO_IS_HIRING=False,
        ENABLE_JOBICY=False,
        ENABLE_WE_WORK_REMOTELY=False,
        ENABLE_HIMALAYAS=False,
        ENABLE_REAL_WORK_FROM_ANYWHERE=False,
        ENABLE_JOBSCOLLIDER=False,
        ENABLE_JOBSPY_LINKEDIN=False,
    )

    class FakeAdapter:
        name = "LinkedIn Hiring Posts"

        async def fetch(self):
            return [
                Vacancy(
                    title="Ищем Junior Front-End Developer",
                    description="Angular TypeScript role in Almaty.",
                    source=self.name,
                    url="https://www.linkedin.com/posts/example",
                ),
                Vacancy(
                    title="Sales Manager",
                    description="B2B sales role.",
                    source=self.name,
                    url="https://www.linkedin.com/posts/sales",
                ),
            ]

    class ExplodingPublisher:
        def __init__(self, settings, store) -> None:
            raise AssertionError("preview-sources must not create TelegramPublisher")

    monkeypatch.setattr("tg_vacancy_bot.app.get_settings", lambda: settings)
    monkeypatch.setattr("tg_vacancy_bot.app.build_adapters", lambda _: [FakeAdapter()])
    monkeypatch.setattr("tg_vacancy_bot.app.TelegramPublisher", ExplodingPublisher)

    main(["preview-sources"])

    output = capsys.readouterr().out
    assert "Source preview" in output
    assert "LinkedIn Hiring Posts: fetched=2 filtered=1" in output
    assert "Ищем Junior Front-End Developer" in output
    assert "https://www.linkedin.com/posts/example" in output
    assert "Sales Manager" not in output


def test_preview_sources_supports_source_filter_and_limit(capsys, monkeypatch) -> None:
    settings = Settings(TELEGRAM_BOT_TOKEN="token", TARGET_CHAT_ID="@target")

    class FirstAdapter:
        name = "First"

        async def fetch(self):
            return [Vacancy(title="Python Engineer", description="Backend role.", source=self.name)]

    class SecondAdapter:
        name = "Second"

        async def fetch(self):
            return [
                Vacancy(title="Frontend Developer", description="React role.", source=self.name),
                Vacancy(title="Backend Developer", description="Python role.", source=self.name),
            ]

    monkeypatch.setattr("tg_vacancy_bot.app.get_settings", lambda: settings)
    monkeypatch.setattr("tg_vacancy_bot.app.build_adapters", lambda _: [FirstAdapter(), SecondAdapter()])

    main(["preview-sources", "--source", "Second", "--limit", "1"])

    output = capsys.readouterr().out
    assert "First:" not in output
    assert "Second: fetched=2 filtered=2" in output
    assert "Frontend Developer" in output
    assert "Backend Developer" not in output


def test_preview_sources_shows_configuration_warning_when_adapter_is_missing(
    capsys,
    monkeypatch,
) -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_REMOTIVE=False,
        ENABLE_ARBEITNOW=False,
        ENABLE_REMOTEOK=False,
        ENABLE_HN_WHO_IS_HIRING=False,
        ENABLE_JOBICY=False,
        ENABLE_WE_WORK_REMOTELY=False,
        ENABLE_HIMALAYAS=False,
        ENABLE_REAL_WORK_FROM_ANYWHERE=False,
        ENABLE_JOBSCOLLIDER=False,
        ENABLE_JOBSPY_LINKEDIN=False,
        ENABLE_LINKEDIN_POST_SEARCH=True,
        ENABLE_LINKEDIN_POST_SCRAPER=False,
        SERPAPI_API_KEY="",
    )
    monkeypatch.setattr("tg_vacancy_bot.app.get_settings", lambda: settings)

    main(["preview-sources", "--source", "LinkedIn Hiring Posts"])

    output = capsys.readouterr().out
    assert "Source preview" in output
    assert "WARNING: LinkedIn Hiring Posts source is enabled but SERPAPI_API_KEY is missing." in output
    assert "No matching registered adapters." in output


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
        ENABLE_JOBSPY_LINKEDIN=False,
        ENABLE_LINKEDIN_POST_SEARCH=True,
        ENABLE_LINKEDIN_POST_SCRAPER=False,
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
