import asyncio
from datetime import UTC, datetime, timedelta

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.sources.adapters.linkedin_jobs_guest import (
    LinkedInJobsGuestAdapter,
    parse_guest_job_cards,
)


def _card_html(
    title: str = "Junior Frontend Developer",
    job_id: str = "4457383307",
    posted: str = "2026-08-21",
    company: str = "Example Corp",
    location: str = "Remote",
) -> str:
    return f"""
    <html><body>
      <li>
        <div class="base-card">
          <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/junior-frontend-{job_id}?trk=x">
            <span class="sr-only">{title}</span>
          </a>
          <div class="base-search-card__info">
            <h3 class="base-search-card__title">{title}</h3>
            <h4 class="base-search-card__subtitle">{company}</h4>
            <div class="base-search-card__metadata">
              <span class="job-search-card__location">{location}</span>
              <time class="job-search-card__listdate" datetime="{posted}">2 weeks ago</time>
            </div>
          </div>
        </div>
      </li>
    </body></html>
    """


def _job_page_html(description: str) -> str:
    return f"""
    <html><body>
      <div class="show-more-less-html__markup">{description}</div>
    </body></html>
    """


def test_parse_guest_job_cards_keeps_only_junior_frontend_fullstack_titles() -> None:
    html = _card_html() + """
    <li>
      <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/senior-frontender-123"></a>
      <h3 class="base-search-card__title">Senior Frontend Developer</h3>
    </li>
    <li>
      <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/data-analyst-124"></a>
      <h3 class="base-search-card__title">Junior Data Analyst</h3>
    </li>
    """

    cards = parse_guest_job_cards(html)

    assert [card.title for card in cards] == ["Junior Frontend Developer"]


def test_parse_guest_job_cards_reads_metadata_and_date() -> None:
    cards = parse_guest_job_cards(_card_html())

    assert len(cards) == 1
    card = cards[0]
    assert card.url == "https://www.linkedin.com/jobs/view/junior-frontend-4457383307"
    assert card.company == "Example Corp"
    assert card.location == "Remote"
    assert card.posted_date == datetime(2026, 8, 21, tzinfo=UTC)


def test_fetch_reads_pages_and_publishes_fresh_vacancies(monkeypatch) -> None:
    monkeypatch.setattr("tg_vacancy_bot.sources.adapters.linkedin_jobs_guest.SEARCH_PAGE_DELAY_SECONDS", 0)
    monkeypatch.setattr("tg_vacancy_bot.sources.adapters.linkedin_jobs_guest.JOB_READ_DELAY_SECONDS", 0)
    fixed_now = datetime.now(UTC)
    recent = (fixed_now - timedelta(days=3)).strftime("%Y-%m-%d")

    search_html = _card_html(posted=recent)

    class FakeResponse:
        status = 200

        def __init__(self, text: str) -> None:
            self._text = text

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        def raise_for_status(self) -> None:
            return None

        async def text(self) -> str:
            return self._text

    class FakeSession:
        def __init__(self) -> None:
            self.get_urls: list[str] = []

        def get(self, url: str, params: dict | None = None):
            self.get_urls.append(url)
            if "jobs/api/seeMoreJobPostings/search" in url:
                return FakeResponse(search_html)
            return FakeResponse(
                _job_page_html(
                    "We are hiring a junior frontend developer to build React interfaces."
                )
            )

        async def __aenter__(self):
            raise AssertionError("not a context manager")

    session = FakeSession()

    def fake_source_session(**kwargs):
        class _Ctx:
            async def __aenter__(self):
                return session

            async def __aexit__(self, *args: object) -> None:
                return None

        return _Ctx()

    monkeypatch.setattr(
        "tg_vacancy_bot.sources.adapters.linkedin_jobs_guest.source_session",
        fake_source_session,
    )
    settings = Settings(
        ENABLE_LINKEDIN_JOBS_GUEST="true",
        LINKEDIN_JOBS_GUEST_KEYWORDS="junior frontend developer||junior fullstack developer",
        LINKEDIN_POST_MAX_AGE_HOURS="240",
    )
    adapter = LinkedInJobsGuestAdapter(settings)

    vacancies = asyncio.run(adapter.fetch())

    assert len(vacancies) == 1
    vacancy = vacancies[0]
    assert vacancy.url.startswith("https://www.linkedin.com/jobs/view/")
    assert vacancy.source == LinkedInJobsGuestAdapter.name
    assert "React interfaces." in vacancy.description
    assert vacancy.location == "Remote"
    assert vacancy.published_at is not None
    # Two keywords deduplicate to one listing; each read hits the job page.
    assert session.get_urls.count(vacancy.url) == 1


def test_fetch_returns_empty_when_search_yields_nothing(monkeypatch) -> None:
    class EmptySession:
        def get(self, url: str, params: dict | None = None):
            class _R:
                def raise_for_status(self) -> None:
                    return None

                async def text(self) -> str:
                    return "<html></html>"

            return _R()

    def fake_source_session(**kwargs):
        class _Ctx:
            async def __aenter__(self):
                return EmptySession()

            async def __aexit__(self, *args: object) -> None:
                return None

        return _Ctx()

    monkeypatch.setattr(
        "tg_vacancy_bot.sources.adapters.linkedin_jobs_guest.source_session",
        fake_source_session,
    )
    settings = Settings(ENABLE_LINKEDIN_JOBS_GUEST="true")
    adapter = LinkedInJobsGuestAdapter(settings)

    assert asyncio.run(adapter.fetch()) == []
