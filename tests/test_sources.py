from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.sources import build_adapters, filter_it_vacancies


def test_build_adapters_skips_keyed_sources_without_credentials() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_REMOTIVE=False,
        ENABLE_ARBEITNOW=False,
        ENABLE_REMOTEOK=False,
        ENABLE_HN_WHO_IS_HIRING=False,
    )

    assert build_adapters(settings) == []


def test_build_adapters_adds_keyed_sources_with_credentials() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_REMOTIVE=False,
        ENABLE_ARBEITNOW=False,
        ENABLE_REMOTEOK=False,
        ENABLE_HN_WHO_IS_HIRING=False,
        ADZUNA_APP_ID="app",
        ADZUNA_APP_KEY="key",
        JOOBLE_API_KEY="jooble",
    )

    names = [adapter.name for adapter in build_adapters(settings)]

    assert names == ["Adzuna", "Jooble"]


def test_filter_it_vacancies_rejects_courses() -> None:
    vacancies = [
        Vacancy(title="Python Developer", description="Remote backend role", source="Test"),
        Vacancy(title="Python course", description="Bootcamp for beginners", source="Test"),
    ]

    filtered = filter_it_vacancies(vacancies)

    assert [vacancy.title for vacancy in filtered] == ["Python Developer"]
