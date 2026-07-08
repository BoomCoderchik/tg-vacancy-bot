import asyncio
from datetime import UTC, datetime

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.sources import build_adapters, filter_it_vacancies
from tg_vacancy_bot.sources.adapters.jobicy import JobicyAdapter
from tg_vacancy_bot.sources.rss import RssFeedAdapter, RssFeedConfig


def test_build_adapters_skips_keyed_sources_without_credentials() -> None:
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
        ENABLE_JOBICY=False,
        ENABLE_WE_WORK_REMOTELY=False,
        ENABLE_HIMALAYAS=False,
        ENABLE_REAL_WORK_FROM_ANYWHERE=False,
        ENABLE_JOBSCOLLIDER=False,
        ADZUNA_APP_ID="app",
        ADZUNA_APP_KEY="key",
        JOOBLE_API_KEY="jooble",
    )

    names = [adapter.name for adapter in build_adapters(settings)]

    assert names == ["Adzuna", "Jooble"]


def test_build_adapters_adds_no_key_sources_by_default() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_REMOTIVE=False,
        ENABLE_ARBEITNOW=False,
        ENABLE_REMOTEOK=False,
        ENABLE_HN_WHO_IS_HIRING=False,
    )

    names = [adapter.name for adapter in build_adapters(settings)]

    assert names == [
        "Jobicy",
        "We Work Remotely",
        "Himalayas",
        "Real Work From Anywhere",
        "JobsCollider",
    ]


def test_jobicy_adapter_maps_public_api_response(monkeypatch) -> None:
    monkeypatch.setattr(
        "tg_vacancy_bot.sources.adapters.jobicy.source_session",
        lambda: _FakeSession(
            json_data={
                "jobs": [
                    {
                        "jobTitle": "Senior Python Developer",
                        "companyName": "Example Co",
                        "jobGeo": "Worldwide",
                        "jobDescription": "<p>Build Python APIs with FastAPI.</p>",
                        "url": "https://jobicy.com/jobs/example",
                        "jobIndustry": ["Software Engineering"],
                        "pubDate": "2026-07-06T16:25:02+00:00",
                    }
                ]
            }
        ),
    )

    vacancies = asyncio.run(JobicyAdapter().fetch())

    assert vacancies == [
        Vacancy(
            title="Senior Python Developer",
            company="Example Co",
            location="Worldwide",
            description="Build Python APIs with FastAPI.",
            source="Jobicy",
            url="https://jobicy.com/jobs/example",
            stack=("Software Engineering", "Python", "FastAPI"),
            published_at=datetime(2026, 7, 6, 16, 25, 2, tzinfo=UTC),
            raw_text="Build Python APIs with FastAPI.",
        )
    ]


def test_rss_feed_adapter_maps_public_feed_item(monkeypatch) -> None:
    monkeypatch.setattr(
        "tg_vacancy_bot.sources.rss.source_session",
        lambda: _FakeSession(
            text_data="""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Backend Engineer at Example Co</title>
      <link>https://example.com/jobs/backend</link>
      <description><![CDATA[<p>Remote backend work with Python and FastAPI.</p>]]></description>
      <pubDate>Mon, 06 Jul 2026 16:25:02 +0000</pubDate>
    </item>
  </channel>
</rss>"""
        ),
    )

    vacancies = asyncio.run(
        RssFeedAdapter(RssFeedConfig(source_name="Example RSS", url="https://example.com/feed.xml")).fetch()
    )

    assert vacancies == [
        Vacancy(
            title="Backend Engineer at Example Co",
            company="Example Co",
            location="Remote",
            description="Remote backend work with Python and FastAPI.",
            source="Example RSS",
            url="https://example.com/jobs/backend",
            stack=("Python", "FastAPI"),
            published_at=datetime(2026, 7, 6, 16, 25, 2, tzinfo=UTC),
            raw_text="Remote backend work with Python and FastAPI.",
        )
    ]


def test_filter_it_vacancies_rejects_courses() -> None:
    vacancies = [
        Vacancy(title="Python Developer", description="Remote backend role", source="Test"),
        Vacancy(title="Python course", description="Bootcamp for beginners", source="Test"),
    ]

    filtered = filter_it_vacancies(vacancies)

    assert [vacancy.title for vacancy in filtered] == ["Python Developer"]


def test_filter_it_vacancies_allows_only_development_design_and_ai_roles() -> None:
    vacancies = [
        Vacancy(title="Backend Engineer", description="Python API role", source="Test"),
        Vacancy(title="Frontend Developer", description="React UI role", source="Test"),
        Vacancy(title="Product Designer", description="Design systems and UX", source="Test"),
        Vacancy(title="LLM Engineer", description="Build AI agents", source="Test"),
        Vacancy(title="Fullstack Developer", description="Node.js and React", source="Test"),
        Vacancy(title="Product Manager", description="Software roadmap role", source="Test"),
        Vacancy(title="QA Engineer", description="Manual testing for web app", source="Test"),
        Vacancy(title="DevOps Engineer", description="Kubernetes platform role", source="Test"),
    ]

    filtered = filter_it_vacancies(vacancies)

    assert [vacancy.title for vacancy in filtered] == [
        "Backend Engineer",
        "Frontend Developer",
        "Product Designer",
        "LLM Engineer",
        "Fullstack Developer",
    ]


def test_filter_it_vacancies_rejects_cleaner_at_it_company() -> None:
    vacancies = [
        Vacancy(
            title="Cleaner at IT company",
            description="Office cleaning role for a software platform company.",
            source="Test",
        ),
        Vacancy(
            title="Уборщик в IT компанию",
            description="Работа в офисе software company.",
            source="Test",
        ),
    ]

    assert filter_it_vacancies(vacancies) == []


class _FakeResponse:
    def __init__(self, text_data: str = "", json_data: dict | None = None) -> None:
        self._text_data = text_data
        self._json_data = json_data or {}

    async def __aenter__(self) -> "_FakeResponse":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    async def text(self) -> str:
        return self._text_data

    async def json(self) -> dict:
        return self._json_data


class _FakeSession:
    def __init__(self, text_data: str = "", json_data: dict | None = None) -> None:
        self._response = _FakeResponse(text_data=text_data, json_data=json_data)

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def get(self, url: str) -> _FakeResponse:
        return self._response
