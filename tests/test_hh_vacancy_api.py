import asyncio
from datetime import UTC, datetime

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.sources.adapters import hh_vacancy_api
from tg_vacancy_bot.sources.adapters.hh_vacancy_api import (
    HeadHunterApiAdapter,
    _items_to_vacancies,
    _split_queries,
)


def _api_item(
    *,
    title="Стажер Frontend-разработчик",
    url="https://hh.ru/vacancy/136646186",
    company="Заряд",
    region="Краснодар",
    salary=None,
    published_at="2026-09-16T10:00:00+03:00",
    requirement="Знание JavaScript",
    responsibility="Верстать интерфейсы",
):
    return {
        "name": title,
        "alternate_url": url,
        "employer": {"name": company},
        "area": {"name": region},
        "salary": salary,
        "snippet": {"requirement": requirement, "responsibility": responsibility},
        "published_at": published_at,
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
            query = (params or {}).get("text", "")
            return FakeGet(FakeResponse(data.get(query), statuses.get(query, 200)))

    return FakeSession()


def _install_session(monkeypatch, data, statuses=None):
    session = _make_session(data, statuses)
    monkeypatch.setattr(hh_vacancy_api, "source_session", lambda **kwargs: session)
    return session


def _settings(**overrides):
    values = {
        "ENABLE_HH_API": True,
        "HH_API_CONTACT_EMAIL": "bot@example.com",
        "HH_API_QUERY": "стажер frontend",
        "HH_API_RESULTS_WANTED": 20,
        "SOURCE_MAX_AGE_HOURS": 48,
    }
    values.update(overrides)
    return Settings(**values)


def test_hh_api_maps_item_to_vacancy(monkeypatch) -> None:
    current = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(hh_vacancy_api, "utcnow", lambda: current)
    payload = {
        "items": [
            _api_item(salary={"from": 100000, "to": 150000, "currency": "RUR"}),
        ]
    }
    session = _install_session(monkeypatch, {"стажер frontend": payload})

    vacancies = asyncio.run(HeadHunterApiAdapter(_settings()).fetch())

    assert len(vacancies) == 1
    vacancy = vacancies[0]
    assert vacancy.title == "Стажер Frontend-разработчик"
    assert vacancy.url == "https://hh.ru/vacancy/136646186"
    assert vacancy.source == "HeadHunter API"
    assert vacancy.company == "Заряд"
    assert vacancy.location == "Краснодар"
    assert vacancy.salary == "от 100000 до 150000 \u20bd"
    assert vacancy.published_at is not None
    assert "Знание JavaScript" in vacancy.description
    assert "Верстать интерфейсы" in vacancy.description
    assert session.requested[0][1]["order_by"] == "publication_time"


def test_hh_api_deduplicates_by_url(monkeypatch) -> None:
    current = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(hh_vacancy_api, "utcnow", lambda: current)
    item = _api_item(title="Junior Frontend", url="https://hh.ru/vacancy/9")
    _install_session(monkeypatch, {"стажер frontend": {"items": [item, item]}})

    vacancies = asyncio.run(HeadHunterApiAdapter(_settings()).fetch())

    assert len(vacancies) == 1


def test_hh_api_drops_dated_out_items(monkeypatch) -> None:
    current = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(hh_vacancy_api, "utcnow", lambda: current)
    old_item = _api_item(
        title="Старый Frontend",
        url="https://hh.ru/vacancy/1",
        published_at="2026-01-01T10:00:00+03:00",
    )
    fresh_item = _api_item(title="Свежий Frontend", url="https://hh.ru/vacancy/2")
    _install_session(
        monkeypatch, {"стажер frontend": {"items": [old_item, fresh_item]}}
    )

    vacancies = asyncio.run(HeadHunterApiAdapter(_settings()).fetch())

    assert [v.title for v in vacancies] == ["Свежий Frontend"]


def test_hh_api_items_to_vacancies_ignores_malformed_payload() -> None:
    assert _items_to_vacancies(None, set()) == []
    assert _items_to_vacancies({}, set()) == []
    assert _items_to_vacancies({"items": "nope"}, set()) == []
    assert _items_to_vacancies({"items": [{"name": "", "alternate_url": ""}]}, set()) == []


def test_hh_api_missing_query_or_contact_returns_empty(monkeypatch) -> None:
    assert asyncio.run(HeadHunterApiAdapter(_settings(HH_API_QUERY="")).fetch()) == []
    assert (
        asyncio.run(HeadHunterApiAdapter(_settings(HH_API_CONTACT_EMAIL="")).fetch())
        == []
    )


def test_hh_api_split_queries() -> None:
    assert _split_queries("one || two") == ("one", "two")
    assert _split_queries("") == ()
