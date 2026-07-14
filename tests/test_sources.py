import asyncio
from datetime import UTC, datetime

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.sources import build_adapters, filter_it_vacancies
from tg_vacancy_bot.sources.adapters.linkedin_post_scraper import (
    LinkedInPostScraperAdapter,
    _html_to_vacancies,
)
from tg_vacancy_bot.sources.adapters.linkedin_post_search import LinkedInPostSearchAdapter, LinkedInPostSerperAdapter
from tg_vacancy_bot.sources.adapters.jobspy_linkedin import JobSpyLinkedInAdapter
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
        ENABLE_JOBSPY_LINKEDIN=False,
        ENABLE_LINKEDIN_POST_SCRAPER=False,
        SERPER_API_KEY="",
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
        ENABLE_JOBSPY_LINKEDIN=False,
        ENABLE_LINKEDIN_POST_SCRAPER=False,
        SERPER_API_KEY="",
        ADZUNA_APP_ID="app",
        ADZUNA_APP_KEY="key",
        JOOBLE_API_KEY="jooble",
    )

    names = [adapter.name for adapter in build_adapters(settings)]

    assert names == ["Adzuna", "Jooble"]


def test_build_adapters_adds_jobspy_linkedin_when_enabled() -> None:
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
        ENABLE_LINKEDIN_POST_SCRAPER=False,
        ENABLE_JOBSPY_LINKEDIN=True,
        SERPER_API_KEY="",
    )

    names = [adapter.name for adapter in build_adapters(settings)]

    assert names == ["JobSpy LinkedIn"]


def test_build_adapters_adds_linkedin_post_search_with_serpapi_key() -> None:
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
        SERPAPI_API_KEY="serp-key",
        SERPER_API_KEY="",
    )

    names = [adapter.name for adapter in build_adapters(settings)]

    assert names == ["LinkedIn Hiring Posts"]


def test_build_adapters_adds_linkedin_post_search_with_serper_key() -> None:
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
        SERPER_API_KEY="serper-key",
    )

    names = [adapter.name for adapter in build_adapters(settings)]

    assert names == ["LinkedIn Hiring Posts (Serper)"]


def test_build_adapters_skips_linkedin_post_search_without_search_provider_key() -> None:
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
        SERPER_API_KEY="",
    )

    assert build_adapters(settings) == []


def test_build_adapters_adds_linkedin_post_scraper_without_api_key() -> None:
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
        ENABLE_LINKEDIN_POST_SEARCH=False,
        ENABLE_LINKEDIN_POST_SCRAPER=True,
    )

    names = [adapter.name for adapter in build_adapters(settings)]

    assert names == ["LinkedIn Hiring Post Scraper"]


def test_build_adapters_adds_no_key_sources_by_default() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_REMOTIVE=False,
        ENABLE_ARBEITNOW=False,
        ENABLE_REMOTEOK=False,
        ENABLE_HN_WHO_IS_HIRING=False,
        ENABLE_JOBSPY_LINKEDIN=False,
        ENABLE_LINKEDIN_POST_SCRAPER=False,
        SERPER_API_KEY="",
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


def test_jobspy_linkedin_adapter_maps_jobspy_records(monkeypatch) -> None:
    calls = []

    class FakeFrame:
        def to_dict(self, orient: str):
            assert orient == "records"
            return [
                {
                    "title": "Senior Backend Engineer",
                    "company": "Example Co",
                    "job_url": "https://www.linkedin.com/jobs/view/123",
                    "location": "Remote",
                    "description": "Build Python APIs with FastAPI.",
                    "date_posted": "2026-07-08",
                    "is_remote": True,
                    "job_type": "fulltime",
                    "emails": ["jobs@example.com"],
                },
                {
                    "title": "",
                    "job_url": "",
                },
            ]

    def fake_scrape_jobs(**kwargs):
        calls.append(kwargs)
        return FakeFrame()

    monkeypatch.setattr(
        "tg_vacancy_bot.sources.adapters.jobspy_linkedin._load_scrape_jobs",
        lambda: fake_scrape_jobs,
    )

    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        JOBSPY_LINKEDIN_QUERY="backend OR frontend",
        JOBSPY_LINKEDIN_LOCATION="Worldwide",
        JOBSPY_LINKEDIN_RESULTS_WANTED="5",
        JOBSPY_LINKEDIN_HOURS_OLD="24",
        JOBSPY_LINKEDIN_PROXIES="http://proxy-a,http://proxy-b",
    )

    vacancies = asyncio.run(JobSpyLinkedInAdapter(settings).fetch())

    assert calls == [
        {
            "site_name": "linkedin",
            "search_term": "backend OR frontend",
            "location": "Worldwide",
            "results_wanted": 5,
            "hours_old": 24,
            "is_remote": True,
            "linkedin_fetch_description": False,
            "proxies": ["http://proxy-a", "http://proxy-b"],
            "verbose": 0,
        }
    ]
    assert vacancies == [
        Vacancy(
            title="Senior Backend Engineer",
            company="Example Co",
            location="Remote",
            description="Build Python APIs with FastAPI.",
            source="JobSpy LinkedIn",
            url="https://www.linkedin.com/jobs/view/123",
            stack=("LinkedIn", "Remote", "fulltime", "jobs@example.com"),
            published_at=datetime(2026, 7, 8, tzinfo=UTC),
            raw_text="Senior Backend Engineer Example Co Remote Build Python APIs with FastAPI.",
        )
    ]


def test_linkedin_post_search_adapter_maps_public_post_results(monkeypatch) -> None:
    calls = []

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def get(self, url: str, params: dict):
            calls.append((url, params))
            return _FakeResponse(
                json_data={
                    "organic_results": [
                        {
                            "title": "Ищем Junior Front-End Developer в команду DAP | LinkedIn",
                            "link": "https://www.linkedin.com/posts/example_hiring-junior-frontend-activity-123",
                            "snippet": (
                                "г. Алматы. Ищем Junior Front-End Developer. "
                                "Angular от 1 года, TypeScript, HTML/CSS. Резюме: hr@example.kz"
                            ),
                            "date": "Jul 8, 2026",
                        },
                        {
                            "title": "Senior Backend Engineer",
                            "link": "https://www.linkedin.com/jobs/view/123",
                            "snippet": "Regular LinkedIn job page, not a post.",
                        },
                    ]
                }
            )

    monkeypatch.setattr(
        "tg_vacancy_bot.sources.adapters.linkedin_post_search.source_session",
        lambda: FakeSession(),
    )

    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_LINKEDIN_POST_SEARCH=True,
        SERPAPI_API_KEY="serp-key",
        LINKEDIN_POST_SEARCH_QUERY='site:linkedin.com/posts "Ищем" frontend',
        LINKEDIN_POST_SEARCH_LOCATION="Kazakhstan",
        LINKEDIN_POST_SEARCH_RESULTS_WANTED="5",
    )

    vacancies = asyncio.run(LinkedInPostSearchAdapter(settings).fetch())

    assert calls == [
        (
            "https://serpapi.com/search.json",
            {
                "engine": "google",
                "api_key": "serp-key",
                "q": 'site:linkedin.com/posts "Ищем" frontend',
                "num": 5,
                "location": "Kazakhstan",
                "hl": "ru",
            },
        )
    ]
    assert vacancies == [
        Vacancy(
            title="Junior Front-End Developer",
            description=(
                "г. Алматы. Ищем Junior Front-End Developer. "
                "Angular от 1 года, TypeScript, HTML/CSS. Резюме: hr@example.kz"
            ),
            source="LinkedIn Hiring Posts",
            url="https://www.linkedin.com/posts/example_hiring-junior-frontend-activity-123",
            location="Kazakhstan",
            stack=("LinkedIn post", "frontend", "Angular", "TypeScript"),
            published_at=datetime(2026, 7, 8, tzinfo=UTC),
            raw_text=(
                "Junior Front-End Developer "
                "г. Алматы. Ищем Junior Front-End Developer. "
                "Angular от 1 года, TypeScript, HTML/CSS. Резюме: hr@example.kz"
            ),
        )
    ]


def test_linkedin_post_search_adapter_tries_fallback_queries_and_dedupes(monkeypatch) -> None:
    calls = []

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def get(self, url: str, params: dict):
            calls.append(params["q"])
            if params["q"] == "first":
                rows = [
                    {
                        "title": "Backend Engineer | LinkedIn",
                        "link": "https://www.linkedin.com/posts/backend-activity-123",
                        "snippet": "We are hiring a Backend Engineer with Python.",
                    }
                ]
            else:
                rows = [
                    {
                        "title": "Backend Engineer | LinkedIn",
                        "link": "https://www.linkedin.com/posts/backend-activity-123",
                        "snippet": "Duplicate backend post.",
                    },
                    {
                        "title": "Frontend Developer | LinkedIn",
                        "link": "https://www.linkedin.com/posts/frontend-activity-456",
                        "snippet": "Looking for a Frontend Developer with React.",
                    },
                ]
            return _FakeResponse(json_data={"organic_results": rows})

    monkeypatch.setattr(
        "tg_vacancy_bot.sources.adapters.linkedin_post_search.source_session",
        lambda: FakeSession(),
    )

    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_LINKEDIN_POST_SEARCH=True,
        SERPAPI_API_KEY="serp-key",
        LINKEDIN_POST_SEARCH_QUERY="first || second",
        LINKEDIN_POST_SEARCH_LOCATION="Kazakhstan",
        LINKEDIN_POST_SEARCH_RESULTS_WANTED="5",
    )

    vacancies = asyncio.run(LinkedInPostSearchAdapter(settings).fetch())

    assert calls == ["first", "second"]
    assert [vacancy.url for vacancy in vacancies] == [
        "https://www.linkedin.com/posts/backend-activity-123",
        "https://www.linkedin.com/posts/frontend-activity-456",
    ]


def test_linkedin_post_serper_adapter_maps_public_post_results(monkeypatch) -> None:
    calls = []

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def post(self, url: str, json: dict):
            calls.append((url, json))
            return _FakeResponse(
                json_data={
                    "organic": [
                        {
                            "title": "Ищем Junior Front-End Developer в команду DAP | LinkedIn",
                            "link": "https://www.linkedin.com/posts/example_hiring-junior-frontend-activity-123",
                            "snippet": (
                                "г. Алматы. Ищем Junior Front-End Developer. "
                                "Angular от 1 года, TypeScript, HTML/CSS. Резюме: hr@example.kz"
                            ),
                            "date": "Jul 8, 2026",
                        },
                        {
                            "title": "Senior Backend Engineer",
                            "link": "https://www.linkedin.com/jobs/view/123",
                            "snippet": "Regular LinkedIn job page, not a post.",
                        },
                    ]
                }
            )

    monkeypatch.setattr(
        "tg_vacancy_bot.sources.adapters.linkedin_post_search.source_session",
        lambda headers=None: FakeSession(),
    )

    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_LINKEDIN_POST_SEARCH=True,
        SERPER_API_KEY="serper-key",
        LINKEDIN_POST_SEARCH_QUERY='site:linkedin.com/posts "Ищем" frontend',
        LINKEDIN_POST_SEARCH_LOCATION="Kazakhstan",
        LINKEDIN_POST_SEARCH_RESULTS_WANTED="5",
    )

    vacancies = asyncio.run(LinkedInPostSerperAdapter(settings).fetch())

    assert calls == [
        (
            "https://google.serper.dev/search",
            {
                "q": 'site:linkedin.com/posts "Ищем" frontend',
                "num": 5,
                "hl": "ru",
                "location": "Kazakhstan",
            },
        )
    ]
    assert vacancies == [
        Vacancy(
            title="Junior Front-End Developer",
            description=(
                "г. Алматы. Ищем Junior Front-End Developer. "
                "Angular от 1 года, TypeScript, HTML/CSS. Резюме: hr@example.kz"
            ),
            source="LinkedIn Hiring Posts (Serper)",
            url="https://www.linkedin.com/posts/example_hiring-junior-frontend-activity-123",
            location="Kazakhstan",
            stack=("LinkedIn post", "frontend", "Angular", "TypeScript"),
            published_at=datetime(2026, 7, 8, tzinfo=UTC),
            raw_text=(
                "Junior Front-End Developer "
                "г. Алматы. Ищем Junior Front-End Developer. Angular от 1 года, TypeScript, HTML/CSS. "
                "Резюме: hr@example.kz"
            ),
        )
    ]


def test_linkedin_post_serper_adapter_paginates_large_requested_result_count(monkeypatch) -> None:
    calls = []

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def post(self, url: str, json: dict):
            calls.append(json)
            page = json.get("page", 1)
            rows = [
                {
                    "title": f"Backend Engineer {index} | LinkedIn",
                    "link": f"https://www.linkedin.com/posts/backend-{page}-{index}-activity-{page}{index}",
                    "snippet": "We are hiring a Backend Engineer with Python.",
                }
                for index in range(10)
            ]
            return _FakeResponse(json_data={"organic": rows})

    monkeypatch.setattr(
        "tg_vacancy_bot.sources.adapters.linkedin_post_search.source_session",
        lambda headers=None: FakeSession(),
    )
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_LINKEDIN_POST_SEARCH=True,
        SERPER_API_KEY="serper-key",
        LINKEDIN_POST_SEARCH_QUERY="hiring backend engineer",
        LINKEDIN_POST_SEARCH_RESULTS_WANTED="25",
    )

    vacancies = asyncio.run(LinkedInPostSerperAdapter(settings).fetch())

    assert [call["num"] for call in calls] == [10, 10, 5]
    assert [call.get("page") for call in calls] == [None, 2, 3]
    assert len(vacancies) == 25


def test_linkedin_post_scraper_maps_public_search_html(monkeypatch) -> None:
    calls = []
    html = """
    <html>
      <body>
        <a class="result__a" href="/l/?uddg=https%3A%2F%2Fwww.linkedin.com%2Fposts%2Fexample_hiring-junior-frontend-activity-7480965762036461568">
          Ищем Junior Front-End Developer в команду DAP | LinkedIn
        </a>
        <a class="result__snippet">
          г. Алматы. Ищем Junior Front-End Developer. Angular от 1 года, TypeScript, HTML/CSS.
        </a>
        <a class="result__a" href="https://www.linkedin.com/jobs/view/123">
          Senior Backend Engineer
        </a>
        <a class="result__snippet">Regular LinkedIn job page, not a post.</a>
      </body>
    </html>
    """

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def get(self, url: str, params: dict):
            calls.append((url, params))
            return _FakeResponse(text_data=html)

    monkeypatch.setattr(
        "tg_vacancy_bot.sources.adapters.linkedin_post_scraper.source_session",
        lambda headers=None: FakeSession(),
    )

    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_LINKEDIN_POST_SCRAPER=True,
        LINKEDIN_POST_SCRAPER_QUERY='site:linkedin.com/posts "Ищем" frontend',
        LINKEDIN_POST_SCRAPER_LOCATION="Kazakhstan",
        LINKEDIN_POST_SCRAPER_RESULTS_WANTED="5",
    )

    vacancies = asyncio.run(LinkedInPostScraperAdapter(settings).fetch())

    assert calls == [
        (
            "https://html.duckduckgo.com/html/",
            {"q": 'site:linkedin.com/posts "Ищем" frontend'},
        )
    ]
    assert vacancies == [
        Vacancy(
            title="Junior Front-End Developer",
            description="г. Алматы. Ищем Junior Front-End Developer. Angular от 1 года, TypeScript, HTML/CSS.",
            source="LinkedIn Hiring Post Scraper",
            url="https://www.linkedin.com/posts/example_hiring-junior-frontend-activity-7480965762036461568",
            location="Kazakhstan",
            stack=("LinkedIn post", "frontend", "Angular", "TypeScript"),
            published_at=datetime(2026, 7, 9, 12, 47, 7, 292000, tzinfo=UTC),
            raw_text=(
                "Junior Front-End Developer "
                "г. Алматы. Ищем Junior Front-End Developer. Angular от 1 года, TypeScript, HTML/CSS."
            ),
        )
    ]


def test_linkedin_post_scraper_uses_role_title_instead_of_hashtags() -> None:
    html = """
    <div class="result">
      <a class="result__a" href="https://www.linkedin.com/posts/example_hiring-software-activity-7480965762036461568">
        #hiring #softwaredeveloper #clouddeveloper #java #python # ... - LinkedIn
      </a>
      <a class="result__snippet">
        Нанимается Software Developer в облачных технологиях. Требуется опыт работы от 10 лет.
      </a>
    </div>
    """

    vacancies = _html_to_vacancies(html, location="Kazakhstan", limit=5)

    assert len(vacancies) == 1
    assert vacancies[0].title == "Software Developer"
    assert vacancies[0].stack == ("LinkedIn post", "Python")


def test_linkedin_post_scraper_skips_results_without_a_reliable_date() -> None:
    html = """
    <a class="result__a" href="https://www.linkedin.com/posts/example_hiring-activity-no-date">
      Hiring developer - LinkedIn
    </a>
    <a class="result__snippet">We are hiring a backend developer.</a>
    """

    assert _html_to_vacancies(html, location="Kazakhstan", limit=5) == []


def test_linkedin_post_scraper_reports_search_challenge(monkeypatch) -> None:
    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def get(self, url: str, params: dict):
            return _FakeResponse(text_data='<form id="challenge-form"></form>')

    monkeypatch.setattr(
        "tg_vacancy_bot.sources.adapters.linkedin_post_scraper.source_session",
        lambda headers=None: FakeSession(),
    )

    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_LINKEDIN_POST_SCRAPER=True,
    )

    try:
        asyncio.run(LinkedInPostScraperAdapter(settings).fetch())
    except RuntimeError as exc:
        assert "anti-bot challenge" in str(exc)
    else:
        raise AssertionError("Expected scraper to report the search provider challenge.")


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

    def post(self, url: str, json: dict) -> _FakeResponse:
        return self._response
