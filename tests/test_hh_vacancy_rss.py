import asyncio
from datetime import UTC, datetime

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.sources.adapters import hh_vacancy_rss
from tg_vacancy_bot.sources.adapters.hh_vacancy_rss import (
    HeadHunterRssAdapter,
    _hh_queries,
    _rss_items_to_vacancies,
)

_RSS_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel>
<title>HeadHunter Vacancy</title>
<link>https://hh.ru</link>
<description>HeadHunter Vacancy</description>
{items}
</channel></rss>
"""

_ITEM_CDATA = """<p>Вакансия компании: {company}</p> <p>Создана: {created}</p> <p>Регион: {region}</p> <p>Предполагаемый уровень месячного дохода: {salary}</p>"""


def _rss_item(
    *,
    title: str,
    url: str,
    company: str = "Яндекс",
    created: str = "14.09.2026",
    region: str = "Москва",
    salary: str = "до 75 000 ₽",
    pub_date: str = "2026-09-14T10:28:34.481+03:00",
) -> str:
    description = _ITEM_CDATA.format(company=company, created=created, region=region, salary=salary)
    return (
        f"<item>"
        f"<title>{title}</title>"
        f"<link>{url}</link>"
        f"<guid isPermaLink='true'>{url}</guid>"
        f"<pubDate>{pub_date}</pubDate>"
        f"<description><![CDATA[{description}]]></description>"
        f"</item>"
    )


def _make_session(data, statuses=None):
    statuses = statuses or {}

    class FakeResponse:
        def __init__(self, text, status):
            self._text = text
            self.status = status

        def raise_for_status(self):
            if self.status >= 400:
                raise RuntimeError(f"HTTP {self.status}")

        async def text(self):
            return self._text

    class FakeGet:
        def __init__(self, response):
            self._response = response

        async def __aenter__(self):
            return self._response

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return False

    class FakeSession:
        def __init__(self):
            self.requested = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return False

        def get(self, url, params=None):
            self.requested.append((url, params))
            query = (params or {}).get("text", "")
            return FakeGet(FakeResponse(data.get(query, ""), statuses.get(query, 200)))

    return FakeSession()


def _install_session(monkeypatch, data, statuses=None):
    session = _make_session(data, statuses)
    monkeypatch.setattr(hh_vacancy_rss, "source_session", lambda **kwargs: session)
    return session


def test_hh_rss_maps_item_to_vacancy(monkeypatch) -> None:
    current = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(hh_vacancy_rss, "utcnow", lambda: current)
    item = _rss_item(
        title="Стажер Frontend-разработчик",
        url="https://hh.ru/vacancy/136646186",
        company="Заряд",
        created="14.09.2026",
        region="Краснодар",
        salary="не указан",
    )
    rss = _RSS_TEMPLATE.format(items=item)
    _install_session(monkeypatch, {"стажер frontend-разработчик": rss})

    settings = Settings(
        ENABLE_HHRU_RSS=True,
        HHRU_RSS_QUERY="стажер frontend-разработчик",
        HHRU_RSS_RESULTS_WANTED=20,
        SOURCE_MAX_AGE_HOURS=48,
    )
    vacancies = asyncio.run(HeadHunterRssAdapter(settings).fetch())

    assert len(vacancies) == 1
    vacancy = vacancies[0]
    assert vacancy.title == "Стажер Frontend-разработчик"
    assert vacancy.url == "https://hh.ru/vacancy/136646186"
    assert vacancy.source == "HeadHunter RSS"
    assert vacancy.company == "Заряд"
    assert vacancy.location == "Краснодар"
    assert vacancy.salary is None
    assert vacancy.published_at is not None
    assert "Вакансия компании" in vacancy.description


def test_hh_rss_deduplicates_by_url(monkeypatch) -> None:
    current = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(hh_vacancy_rss, "utcnow", lambda: current)
    item = _rss_item(
        title="Junior Full Stack Developer",
        url="https://hh.ru/vacancy/136309811",
        region="Покровка",
        salary="от 88 000 до 145 000 ₽",
    )
    rss = _RSS_TEMPLATE.format(items=item + item)
    _install_session(monkeypatch, {"junior full stack developer": rss})

    settings = Settings(
        ENABLE_HHRU_RSS=True,
        HHRU_RSS_QUERY="junior full stack developer",
        SOURCE_MAX_AGE_HOURS=48,
    )
    vacancies = asyncio.run(HeadHunterRssAdapter(settings).fetch())

    assert len(vacancies) == 1


def test_hh_rss_drops_dated_out_items(monkeypatch) -> None:
    current = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(hh_vacancy_rss, "utcnow", lambda: current)
    old_item = _rss_item(
        title="Старый Frontend Junior",
        url="https://hh.ru/vacancy/1",
        created="01.01.2026",
        pub_date="2026-01-01T10:00:00+03:00",
    )
    fresh_item = _rss_item(
        title="Свежий Frontend Junior",
        url="https://hh.ru/vacancy/2",
        created="14.09.2026",
        pub_date="2026-09-14T10:00:00+03:00",
    )
    rss = _RSS_TEMPLATE.format(items=old_item + fresh_item)
    _install_session(monkeypatch, {"свежий и старый junior frontend": rss})

    settings = Settings(
        ENABLE_HHRU_RSS=True,
        HHRU_RSS_QUERY="свежий и старый junior frontend",
        SOURCE_MAX_AGE_HOURS=48,
    )
    vacancies = asyncio.run(HeadHunterRssAdapter(settings).fetch())

    assert [v.title for v in vacancies] == ["Свежий Frontend Junior"]


def test_hh_queries_splits_double_pipe() -> None:
    assert _hh_queries("one || two || three") == ("one", "two", "three")
    assert _hh_queries("  only  ") == ("only",)
    assert _hh_queries("") == ()


def test_hh_queries_double_pipe_empty_internal() -> None:
    assert _hh_queries("one ||  || two") == ("one", "two")


def test_rss_items_to_vacancies_ignores_malformed_feed() -> None:
    assert _rss_items_to_vacancies("", set()) == []
    assert _rss_items_to_vacancies("not xml at all", set()) == []


def test_hh_rss_keeps_salary_when_present(monkeypatch) -> None:
    current = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(hh_vacancy_rss, "utcnow", lambda: current)
    item = _rss_item(
        title="Junior Fullstack-разработчик",
        url="https://hh.ru/vacancy/137043286",
        region="Санкт-Петербург",
        salary="от 60 000 до 90 000 ₽",
    )
    rss = _RSS_TEMPLATE.format(items=item)
    _install_session(monkeypatch, {"junior fullstack-разработчик": rss})

    settings = Settings(
        ENABLE_HHRU_RSS=True,
        HHRU_RSS_QUERY="junior fullstack-разработчик",
        SOURCE_MAX_AGE_HOURS=48,
    )
    vacancies = asyncio.run(HeadHunterRssAdapter(settings).fetch())

    assert vacancies[0].salary == "от 60 000 до 90 000 ₽"


def test_hh_rss_missing_query_returns_empty(monkeypatch) -> None:
    settings = Settings(ENABLE_HHRU_RSS=True, HHRU_RSS_QUERY="")
    vacancies = asyncio.run(HeadHunterRssAdapter(settings).fetch())
    assert vacancies == []