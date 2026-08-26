import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.sources import build_adapters, filter_it_vacancies, source_configuration_warnings
from tg_vacancy_bot.sources.adapters import linkedin_post_scraper
from tg_vacancy_bot.sources.adapters.linkedin_post_search import (
    _filter_recent_linkedin_posts,
    _result_to_vacancy as _search_result_to_vacancy,
)
from tg_vacancy_bot.sources.adapters.linkedin_post_scraper import (
    LinkedInPostScraperAdapter,
    _html_to_vacancies,
    _rss_to_vacancies,
)


def test_build_adapters_registers_no_non_linkedin_sources_by_default() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_LINKEDIN_POST_SEARCH=False,
        ENABLE_LINKEDIN_POST_SCRAPER=False,
        ENABLE_LINKEDIN_JOBS_GUEST=False,
        ENABLE_LINKEDIN_POST_HEADLESS=False,
    )

    assert build_adapters(settings) == []


def test_build_adapters_keeps_opt_in_linkedin_scraper() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_LINKEDIN_POST_SEARCH=False,
        ENABLE_LINKEDIN_POST_SCRAPER=True,
        ENABLE_LINKEDIN_JOBS_GUEST=False,
        ENABLE_LINKEDIN_POST_HEADLESS=False,
    )

    assert [adapter.name for adapter in build_adapters(settings)] == ["LinkedIn Hiring Post Scraper"]


def test_build_adapters_registers_guest_jobs_independent_of_headless() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_LINKEDIN_POST_SEARCH=False,
        ENABLE_LINKEDIN_POST_SCRAPER=False,
        ENABLE_LINKEDIN_POST_HEADLESS=True,
        LINKEDIN_HEADLESS_ACCESS_AUTHORIZED=False,
        LINKEDIN_HEADLESS_PERMISSION_REFERENCE="",
        ENABLE_LINKEDIN_JOBS_GUEST=True,
    )

    assert [adapter.name for adapter in build_adapters(settings)] == ["LinkedIn Jobs (Guest)"]


def test_build_adapters_keeps_headless_disabled_without_authorized_access() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_LINKEDIN_POST_SEARCH=True,
        ENABLE_LINKEDIN_POST_SCRAPER=True,
        ENABLE_LINKEDIN_JOBS_GUEST=False,
        ENABLE_LINKEDIN_POST_HEADLESS=True,
        LINKEDIN_HEADLESS_ACCESS_AUTHORIZED=False,
        SERPAPI_API_KEY="search-key",
    )

    assert build_adapters(settings) == []


def test_build_adapters_keeps_headless_disabled_without_permission_reference() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_LINKEDIN_POST_SEARCH=False,
        ENABLE_LINKEDIN_POST_SCRAPER=False,
        ENABLE_LINKEDIN_JOBS_GUEST=False,
        ENABLE_LINKEDIN_POST_HEADLESS=True,
        LINKEDIN_HEADLESS_ACCESS_AUTHORIZED=True,
        LINKEDIN_HEADLESS_PERMISSION_REFERENCE="",
        SERPAPI_API_KEY="search-key",
    )

    assert build_adapters(settings) == []


def test_build_adapters_registers_only_headless_linkedin_pipeline_when_authorized() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_LINKEDIN_POST_SEARCH=True,
        ENABLE_LINKEDIN_POST_SCRAPER=True,
        ENABLE_LINKEDIN_JOBS_GUEST=False,
        ENABLE_LINKEDIN_POST_HEADLESS=True,
        LINKEDIN_HEADLESS_ACCESS_AUTHORIZED=True,
        LINKEDIN_HEADLESS_PERMISSION_REFERENCE="linkedin-approval-123",
        SERPAPI_API_KEY="search-key",
    )

    assert [adapter.name for adapter in build_adapters(settings)] == [
        "LinkedIn Hiring Posts (Headless)"
    ]
    assert not any("LinkedIn Hiring Posts source" in warning for warning in source_configuration_warnings(settings))


def test_apify_adapter_requires_token_and_registers_when_enabled() -> None:
    missing_token = Settings(
        ENABLE_LINKEDIN_POST_APIFY=True,
        ENABLE_LINKEDIN_POST_HEADLESS=False,
        LINKEDIN_HEADLESS_ACCESS_AUTHORIZED=False,
        LINKEDIN_HEADLESS_PERMISSION_REFERENCE="",
    )
    assert not any(adapter.name == "LinkedIn Hiring Posts (Apify)" for adapter in build_adapters(missing_token))
    assert "APIFY_API_TOKEN is missing" in " ".join(source_configuration_warnings(missing_token))

    configured = Settings(
        ENABLE_LINKEDIN_POST_APIFY=True,
        APIFY_API_TOKEN="test-token",
        ENABLE_LINKEDIN_POST_HEADLESS=False,
        LINKEDIN_HEADLESS_ACCESS_AUTHORIZED=False,
        LINKEDIN_HEADLESS_PERMISSION_REFERENCE="",
    )
    assert any(adapter.name == "LinkedIn Hiring Posts (Apify)" for adapter in build_adapters(configured))


def test_linkedin_scraper_maps_bing_rss_result() -> None:
    rss = """
    <rss><channel><item>
      <title>Hiring Java Developer | LinkedIn</title>
      <link>https://www.linkedin.com/posts/example_hiring-javadeveloper-activity-7482782711737274368-hQ_1</link>
      <description>We are hiring a Java Developer with backend experience.</description>
      <pubDate>Fri, 17 Jul 2026 10:00:00 GMT</pubDate>
    </item></channel></rss>
    """

    vacancies = _rss_to_vacancies(rss, limit=5)

    assert len(vacancies) == 1
    vacancy = vacancies[0]
    assert vacancy.title == "Java Developer"
    assert vacancy.url == "https://www.linkedin.com/posts/example_hiring-javadeveloper-activity-7482782711737274368-hQ_1"
    assert vacancy.description == "We are hiring a Java Developer with backend experience."
    assert vacancy.published_at == datetime(2026, 7, 17, 10, 0, tzinfo=UTC)


def test_linkedin_search_uses_activity_id_when_provider_date_is_missing(monkeypatch) -> None:
    result = {
        "title": "Hiring Python Developer | LinkedIn",
        "link": "https://www.linkedin.com/posts/example_hiring-pythondeveloper-activity-7483822807449600000-hQ_1",
        "snippet": "We are hiring a Python Developer with backend API experience.",
        "date": "",
    }

    vacancy = _search_result_to_vacancy(result, source="LinkedIn Hiring Posts")

    assert vacancy is not None
    assert vacancy.published_at == datetime(2026, 7, 17, 10, 0, tzinfo=UTC)
    monkeypatch.setattr(
        "tg_vacancy_bot.sources.adapters.linkedin_post_search.utcnow",
        lambda: datetime(2026, 7, 18, 9, 0, tzinfo=UTC),
    )
    assert _filter_recent_linkedin_posts([vacancy], max_age_hours=48) == [vacancy]


def test_linkedin_scraper_continues_after_provider_failure(monkeypatch) -> None:
    activity_id = int(datetime.now(UTC).timestamp() * 1000) << 22
    alpha = f"https://www.linkedin.com/posts/alpha_hiring-frontend-activity-{activity_id}-abcd"
    settings = Settings(
        LINKEDIN_POST_SCRAPER_QUERY="site:linkedin.com/posts hiring",
        LINKEDIN_POST_SCRAPER_SEARCH_PROVIDERS="bing_rss,duckduckgo",
        LINKEDIN_POST_SCRAPER_RESULTS_WANTED=10,
        LINKEDIN_POST_MAX_AGE_HOURS=240,
    )

    async def failing_rss(session, query):
        raise RuntimeError("bing rss unavailable")

    html = (
        "<html><body>"
        f"<a class='result__a' href='{alpha}'>Hiring Junior Frontend Developer</a>"
        "<div class='result__snippet'>We are hiring a junior frontend developer.</div>"
        "</body></html>"
    )

    async def working_html(session, provider, query):
        return html

    monkeypatch.setattr(linkedin_post_scraper, "_fetch_bing_rss", failing_rss)
    monkeypatch.setattr(linkedin_post_scraper, "_fetch_search_html", working_html)

    vacancies = asyncio.run(LinkedInPostScraperAdapter(settings).fetch())

    assert len(vacancies) == 1
    assert vacancies[0].url == alpha


def test_linkedin_scraper_raises_when_every_provider_fails(monkeypatch) -> None:
    settings = Settings(
        LINKEDIN_POST_SCRAPER_QUERY="site:linkedin.com/posts hiring",
        LINKEDIN_POST_SCRAPER_SEARCH_PROVIDERS="bing_rss,duckduckgo",
        LINKEDIN_POST_SCRAPER_RESULTS_WANTED=10,
    )

    async def failing_rss(session, query):
        raise RuntimeError("bing rss unavailable")

    async def failing_html(session, provider, query):
        raise RuntimeError(f"{provider} unavailable")

    monkeypatch.setattr(linkedin_post_scraper, "_fetch_bing_rss", failing_rss)
    monkeypatch.setattr(linkedin_post_scraper, "_fetch_search_html", failing_html)

    with pytest.raises(RuntimeError) as exc_info:
        asyncio.run(LinkedInPostScraperAdapter(settings).fetch())

    assert "no usable results" in str(exc_info.value)


def test_linkedin_scraper_parses_mojeek_results() -> None:
    activity_id = int(datetime.now(UTC).timestamp() * 1000) << 22
    url = f"https://www.linkedin.com/posts/hiring_activity-{activity_id}-abcd"
    html = (
        "<html><body><ul class='results-standard'><li>"
        f"<h2><a href='{url}'>Hiring update from ABC Corp</a></h2>"
        "<p class='s'>We are hiring a junior frontend developer to build React UI.</p>"
        "</li></ul></body></html>"
    )

    vacancies = _html_to_vacancies(html, limit=5)

    assert len(vacancies) == 1
    assert vacancies[0].url == url
    assert "frontend" in vacancies[0].title.lower()


def test_linkedin_scraper_treats_mojeek_block_page_as_challenge() -> None:
    from tg_vacancy_bot.sources.adapters.linkedin_post_scraper import _looks_like_search_challenge

    assert _looks_like_search_challenge(
        "<html>Sorry your network appears to be sending automated queries</html>"
    )


def test_linkedin_scraper_decodes_bing_ck_a_redirect_links() -> None:
    import base64

    from tg_vacancy_bot.sources.adapters.linkedin_post_scraper import _normalize_result_url

    target = "https://www.linkedin.com/posts/hiring_activity-7483822807449600000-abcd"
    encoded = base64.urlsafe_b64encode(target.encode()).decode().rstrip("=")
    wrapped = f"https://www.bing.com/ck/a?!&&p=abc&u=a1{encoded}&ntb=1"

    assert _normalize_result_url(wrapped) == target
    assert _normalize_result_url(target) == target


def test_published_at_from_activity_id_supports_feed_update_urn_form() -> None:
    from tg_vacancy_bot.sources.adapters.linkedin_post_scraper import _published_at_from_activity_id

    hyphen = _published_at_from_activity_id(
        "https://www.linkedin.com/posts/x_activity-7483822807449600000-y"
    )
    urn = _published_at_from_activity_id(
        "https://www.linkedin.com/feed/update/urn:li:activity:7483822807449600000/"
    )

    assert hyphen is not None
    assert urn == hyphen


def test_filter_it_vacancies_rejects_courses() -> None:
    vacancies = [
        Vacancy(
            title="Junior Frontend Developer",
            description="We are hiring a junior frontend developer. React.",
            source="Test",
        ),
        Vacancy(title="Frontend course", description="Bootcamp for juniors", source="Test"),
    ]

    assert [vacancy.title for vacancy in filter_it_vacancies(vacancies)] == ["Junior Frontend Developer"]


def test_filter_it_vacancies_allows_only_junior_frontend_fullstack() -> None:
    vacancies = [
        Vacancy(
            title="Junior Frontend Developer",
            description="We are hiring a junior frontend developer to build React UI.",
            source="Test",
        ),
        Vacancy(
            title="Trainee Fullstack Developer",
            description="Join our team as a trainee fullstack developer. Python and React.",
            source="Test",
        ),
        Vacancy(title="Senior Frontend Developer", description="Hiring a senior frontend engineer.", source="Test"),
        Vacancy(title="Backend Engineer", description="Python API role", source="Test"),
        Vacancy(title="Automation QA Engineer", description="Automate tests with Playwright", source="Test"),
        Vacancy(title="Product Manager", description="Software roadmap role", source="Test"),
    ]

    assert [vacancy.title for vacancy in filter_it_vacancies(vacancies)] == [
        "Junior Frontend Developer",
        "Trainee Fullstack Developer",
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

