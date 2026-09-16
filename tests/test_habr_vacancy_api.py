import asyncio
from datetime import UTC, datetime

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.sources.adapters import habr_vacancy_api
from tg_vacancy_bot.sources.adapters.habr_vacancy_api import (
    HabrVacancyApiAdapter,
    _items_to_vacancies,
)


def _api_item(
    *,
    title="Junior Frontend-разработчик",
    href="/vacancies/1000168707",
    company="hirix",
    locations=("Москва",),
    remote=False,
    qualification="Junior",
    salary=None,
    published_date="2026-09-16T11:53:13+03:00",
    divisions=("Frontend-разработка",),
    skills=("React", "TypeScript"),
):
    return {
        "id": 1000168707,
        "href": href,
        "title": title,
        "company": {"title": company},
        "locations": [{"title": name} for name in locations],
        "remoteWork": remote,
        "qualification": qualification,
        "salary": salary or {"from": None, "to": None, "currency": None, "formatted": ""},
        "predictedSalary": {"from": None, "to": None, "currency": None, "formatted": ""},
        "publishedDate": {"date": published_date, "title": "16 сентября"},
        "divisions": [{"title": name} for name in divisions],
        "skills": [{"title": name} for name in skills],
    }


def _make_session(data, statuses=None):
    statuses = statuses or {}

    class FakeResponse:
        def __init__(self, payload, status):
            self._payload = payload
            self.status = status

        def raise_for_status(self):
            if self.status >= 400:
                raise RuntimeError(f"HTTP {self.status}")

        async def json(self):
            return self._payload

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
            query = (params or {}).get("q", "")
            return FakeGet(FakeResponse(data.get(query), statuses.get(query, 200)))

    return FakeSession()


def _install_session(monkeypatch, data, statuses=None):
    session = _make_session(data, statuses)
    monkeypatch.setattr(habr_vacancy_api, "source_session", lambda **kwargs: session)
    return session


def _settings(**overrides):
    values = {
        "ENABLE_HABR_API": True,
        "HABR_API_QUERY": "junior frontend",
        "HABR_API_RESULTS_WANTED": 20,
        "SOURCE_MAX_AGE_HOURS": 48,
    }
    values.update(overrides)
    return Settings(**values)


def test_habr_maps_item_to_vacancy(monkeypatch) -> None:
    current = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(habr_vacancy_api, "utcnow", lambda: current)
    payload = {
        "list": [
            _api_item(
                salary={"from": 80000, "to": 120000, "currency": "rur", "formatted": "от 80 000 до 120 000 \u20bd"},
            )
        ]
    }
    session = _install_session(monkeypatch, {"junior frontend": payload})

    vacancies = asyncio.run(HabrVacancyApiAdapter(_settings()).fetch())

    assert len(vacancies) == 1
    vacancy = vacancies[0]
    assert vacancy.title == "Junior Frontend-разработчик"
    assert vacancy.url == "https://career.habr.com/vacancies/1000168707"
    assert vacancy.source == "Habr Career"
    assert vacancy.company == "hirix"
    assert vacancy.location == "Москва"
    assert vacancy.salary == "от 80 000 до 120 000 \u20bd"
    assert vacancy.stack == ("React", "TypeScript")
    assert vacancy.published_at is not None
    assert "Junior" in vacancy.description
    assert session.requested[0][1]["sort"] == "date"


def test_habr_remote_location_without_cities(monkeypatch) -> None:
    current = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(habr_vacancy_api, "utcnow", lambda: current)
    payload = {"list": [_api_item(locations=(), remote=True)]}
    _install_session(monkeypatch, {"junior frontend": payload})

    vacancies = asyncio.run(HabrVacancyApiAdapter(_settings()).fetch())

    assert vacancies[0].location == "Remote"


def test_habr_drops_dated_out_items(monkeypatch) -> None:
    current = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(habr_vacancy_api, "utcnow", lambda: current)
    old_item = _api_item(
        title="Старый Frontend",
        href="/vacancies/1",
        published_date="2026-01-01T10:00:00+03:00",
    )
    fresh_item = _api_item(title="Свежий Frontend", href="/vacancies/2")
    _install_session(monkeypatch, {"junior frontend": {"list": [old_item, fresh_item]}})

    vacancies = asyncio.run(HabrVacancyApiAdapter(_settings()).fetch())

    assert [v.title for v in vacancies] == ["Свежий Frontend"]


def test_habr_items_to_vacancies_ignores_malformed_payload() -> None:
    assert _items_to_vacancies(None, set()) == []
    assert _items_to_vacancies({}, set()) == []
    assert _items_to_vacancies({"list": "nope"}, set()) == []
    assert _items_to_vacancies({"list": [{"title": "", "href": ""}]}, set()) == []


def test_habr_missing_query_returns_empty() -> None:
    settings = Settings(ENABLE_HABR_API=True, HABR_API_QUERY="")
    assert asyncio.run(HabrVacancyApiAdapter(settings).fetch()) == []
