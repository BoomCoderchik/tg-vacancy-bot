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


def test_build_adapters_adds_linkedin_user_posts_when_feed_is_configured() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TARGET_CHAT_ID="@target",
        ENABLE_REMOTIVE=False,
        ENABLE_ARBEITNOW=False,
        ENABLE_REMOTEOK=False,
        ENABLE_HN_WHO_IS_HIRING=False,
        ENABLE_LINKEDIN_USER_POSTS=True,
        LINKEDIN_USER_POSTS_FEED_URL="https://authorized.example/linkedin-posts.json",
    )

    names = [adapter.name for adapter in build_adapters(settings)]

    assert names == ["LinkedIn user posts"]


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
