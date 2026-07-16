import asyncio
from datetime import UTC, datetime

import pytest

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.sources import build_adapters, filter_it_vacancies
from tg_vacancy_bot.sources.adapters.arbeitnow import ArbeitnowAdapter
from tg_vacancy_bot.sources.adapters.working_nomads import WorkingNomadsAdapter


def test_build_adapters_registers_public_no_account_sources_by_default() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_LINKEDIN_POST_SEARCH=False,
        ENABLE_LINKEDIN_POST_SCRAPER=False,
        ENABLE_LINKEDIN_POST_HEADLESS=False,
    )

    assert [adapter.name for adapter in build_adapters(settings)] == ["Arbeitnow", "Working Nomads"]


def test_build_adapters_allows_disabling_arbeitnow() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_ARBEITNOW=False,
        ENABLE_WORKING_NOMADS=False,
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
        ENABLE_WORKING_NOMADS=False,
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


def test_working_nomads_adapter_maps_public_api_response(monkeypatch) -> None:
    monkeypatch.setattr(
        "tg_vacancy_bot.sources.adapters.working_nomads.source_session",
        lambda: _FakeSession(
            [
                {
                    "title": "Senior Python Developer",
                    "company_name": "Example Co",
                    "location": "Remote - Europe",
                    "description": "<p>Build Python APIs with FastAPI.</p>",
                    "tags": "python, backend",
                    "url": "https://www.workingnomads.com/job/go/123/",
                    "pub_date": "2026-07-10T09:24:39-04:00",
                }
            ]
        ),
    )

    vacancies = asyncio.run(WorkingNomadsAdapter().fetch())

    assert vacancies == [
        Vacancy(
            title="Senior Python Developer",
            company="Example Co",
            location="Remote - Europe",
            description="Build Python APIs with FastAPI.",
            source="Working Nomads",
            url="https://www.workingnomads.com/job/go/123/",
            stack=("python", "backend", "Python", "FastAPI"),
            published_at=datetime(2026, 7, 10, 13, 24, 39, tzinfo=UTC),
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
        Vacancy(title="Trainee Frontend Developer", description="Build React UI", source="Test"),
        Vacancy(title="Automation QA Engineer", description="Automate tests with Playwright", source="Test"),
        Vacancy(title="DevSecOps Engineer", description="Build secure CI checks", source="Test"),
        Vacancy(title="Product Designer", description="Design systems and UX", source="Test"),
        Vacancy(title="Product Manager", description="Software roadmap role", source="Test"),
    ]

    assert [vacancy.title for vacancy in filter_it_vacancies(vacancies)] == [
        "Backend Engineer",
        "Trainee Frontend Developer",
        "Automation QA Engineer",
        "DevSecOps Engineer",
    ]


@pytest.mark.parametrize(
    ("title", "description"),
    [
        ("Embedded Software Engineer", "Develop firmware for robotics devices"),
        ("Solution Architect", "Design software systems for developer teams"),
        ("Engineering Manager", "Lead backend engineers"),
        ("Technical PM", "Coordinate Python developer roadmap"),
        ("Technical Product Manager", "Own API products for developers"),
        ("Technical Project Manager", "Run JavaScript delivery projects"),
        ("SDET", "Build test automation for web services"),
        ("AppSec Engineer", "Secure application code"),
        ("Technical Support Engineer", "Write scripts and support integrations"),
        ("Technical Writer", "Document APIs and write integration scripts"),
        ("Implementation Engineer", "Configure integrations and write scripts"),
        ("Solutions Consultant", "Help customers integrate developer APIs"),
    ],
)
def test_filter_it_vacancies_rejects_policy_excluded_roles(title: str, description: str) -> None:
    vacancies = [Vacancy(title=title, description=description, source="Test")]

    assert filter_it_vacancies(vacancies) == []


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
