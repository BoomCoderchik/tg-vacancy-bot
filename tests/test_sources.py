import asyncio
from datetime import UTC, datetime

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.sources import build_adapters, filter_it_vacancies
from tg_vacancy_bot.sources.adapters.arbeitnow import ArbeitnowAdapter


def test_build_adapters_registers_only_arbeitnow_by_default() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_LINKEDIN_POST_SEARCH=False,
        ENABLE_LINKEDIN_POST_SCRAPER=False,
        ENABLE_LINKEDIN_POST_HEADLESS=False,
    )

    assert [adapter.name for adapter in build_adapters(settings)] == ["Arbeitnow"]


def test_build_adapters_allows_disabling_arbeitnow() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_ARBEITNOW=False,
        ENABLE_LINKEDIN_POST_SEARCH=False,
        ENABLE_LINKEDIN_POST_SCRAPER=False,
        ENABLE_LINKEDIN_POST_HEADLESS=False,
    )

    assert build_adapters(settings) == []


def test_build_adapters_keeps_opt_in_linkedin_scraper() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_ARBEITNOW=False,
        ENABLE_LINKEDIN_POST_SEARCH=False,
        ENABLE_LINKEDIN_POST_SCRAPER=True,
        ENABLE_LINKEDIN_POST_HEADLESS=False,
    )

    assert [adapter.name for adapter in build_adapters(settings)] == ["LinkedIn Hiring Post Scraper"]


def test_arbeitnow_adapter_maps_public_api_response(monkeypatch) -> None:
    monkeypatch.setattr(
        "tg_vacancy_bot.sources.adapters.arbeitnow.source_session",
        lambda: _FakeSession(
            {
                "data": [
                    {
                        "title": "Senior Python Developer",
                        "company_name": "Example Co",
                        "location": "Berlin",
                        "description": "<p>Build Python APIs with FastAPI.</p>",
                        "tags": ["Python", "Remote"],
                        "url": "https://www.arbeitnow.com/view/example",
                        "created_at": 1783355102,
                    }
                ]
            }
        ),
    )

    vacancies = asyncio.run(ArbeitnowAdapter().fetch())

    assert vacancies == [
        Vacancy(
            title="Senior Python Developer",
            company="Example Co",
            location="Berlin",
            description="Build Python APIs with FastAPI.",
            source="Arbeitnow",
            url="https://www.arbeitnow.com/view/example",
            stack=("Python", "Remote", "FastAPI"),
            published_at=datetime(2026, 7, 6, 16, 25, 2, tzinfo=UTC),
            raw_text="Build Python APIs with FastAPI.",
        )
    ]


def test_filter_it_vacancies_rejects_courses() -> None:
    vacancies = [
        Vacancy(title="Python Developer", description="Remote backend role", source="Test"),
        Vacancy(title="Python course", description="Bootcamp for beginners", source="Test"),
    ]

    assert [vacancy.title for vacancy in filter_it_vacancies(vacancies)] == ["Python Developer"]


def test_filter_it_vacancies_allows_only_supported_roles() -> None:
    vacancies = [
        Vacancy(title="Backend Engineer", description="Python API role", source="Test"),
        Vacancy(title="Product Designer", description="Design systems and UX", source="Test"),
        Vacancy(title="Product Manager", description="Software roadmap role", source="Test"),
    ]

    assert [vacancy.title for vacancy in filter_it_vacancies(vacancies)] == [
        "Backend Engineer",
        "Product Designer",
    ]


class _FakeResponse:
    def __init__(self, json_data: dict) -> None:
        self._json_data = json_data

    async def __aenter__(self) -> "_FakeResponse":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    async def json(self) -> dict:
        return self._json_data


class _FakeSession:
    def __init__(self, json_data: dict) -> None:
        self._response = _FakeResponse(json_data)

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def get(self, url: str) -> _FakeResponse:
        return self._response
