import asyncio
from datetime import UTC, datetime

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.sources.adapters import superjob_vacancy_api
from tg_vacancy_bot.sources.adapters.superjob_vacancy_api import (
    SuperJobApiAdapter,
    _items_to_vacancies,
)


def _api_item(
    *,
    title="Junior Frontend-разработчик",
    url="https://www.superjob.ru/vakansii/junior-frontend-25746005.html",
    company="Вектор",
    town="Москва",
    date_published=1789473600,
    payment_from=80000,
    payment_to=120000,
    currency="rub",
    work="Разработка интерфейсов",
    candidat="Знание JavaScript",
    compensation="Офис в центре",
):
    return {
        "id": 25746005,
        "profession": title,
        "link": url,
        "firm_name": company,
        "town": {"id": 4, "title": town},
        "date_published": date_published,
        "payment_from": payment_from,
        "payment_to": payment_to,
        "currency": currency,
        "work": work,
        "candidat": candidat,
        "compensation": compensation,
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
            query = (params or {}).get("keyword", "")
            return FakeGet(FakeResponse(data.get(query), statuses.get(query, 200)))

    return FakeSession()


def _install_session(monkeypatch, data, statuses=None):
    session = _make_session(data, statuses)
    monkeypatch.setattr(superjob_vacancy_api, "source_session", lambda **kwargs: session)
    return session


def _settings(**overrides):
    values = {
        "ENABLE_SUPERJOB_API": True,
        "SUPERJOB_API_KEY": "test-key",
        "SUPERJOB_API_QUERY": "junior frontend",
        "SUPERJOB_API_RESULTS_WANTED": 20,
        "SOURCE_MAX_AGE_HOURS": 48,
    }
    values.update(overrides)
    return Settings(**values)


def test_superjob_maps_item_to_vacancy(monkeypatch) -> None:
    current = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(superjob_vacancy_api, "utcnow", lambda: current)
    payload = {"objects": [_api_item()], "total": 1, "more": False}
    session = _install_session(monkeypatch, {"junior frontend": payload})

    vacancies = asyncio.run(SuperJobApiAdapter(_settings()).fetch())

    assert len(vacancies) == 1
    vacancy = vacancies[0]
    assert vacancy.title == "Junior Frontend-разработчик"
    assert vacancy.url == "https://www.superjob.ru/vakansii/junior-frontend-25746005.html"
    assert vacancy.source == "SuperJob"
    assert vacancy.company == "Вектор"
    assert vacancy.location == "Москва"
    assert vacancy.salary == "от 80000 до 120000 \u20bd"
    assert vacancy.published_at is not None
    assert "Разработка интерфейсов" in vacancy.description
    assert "Знание JavaScript" in vacancy.description
    assert session.requested[0][1]["order_field"] == "date"


def test_superjob_drops_dated_out_items(monkeypatch) -> None:
    current = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(superjob_vacancy_api, "utcnow", lambda: current)
    old_item = _api_item(title="Старый Frontend", url="https://www.superjob.ru/v/1", date_published=1767225600)
    fresh_item = _api_item(title="Свежий Frontend", url="https://www.superjob.ru/v/2")
    _install_session(monkeypatch, {"junior frontend": {"objects": [old_item, fresh_item]}})

    vacancies = asyncio.run(SuperJobApiAdapter(_settings()).fetch())

    assert [v.title for v in vacancies] == ["Свежий Frontend"]


def test_superjob_error_envelope_is_skipped(monkeypatch) -> None:
    _install_session(
        monkeypatch, {"junior frontend": {"error": {"code": 403, "message": "denied"}}}
    )

    vacancies = asyncio.run(SuperJobApiAdapter(_settings()).fetch())

    assert vacancies == []


def test_superjob_items_to_vacancies_ignores_malformed_payload() -> None:
    assert _items_to_vacancies(None, set()) == []
    assert _items_to_vacancies({}, set()) == []
    assert _items_to_vacancies({"objects": "nope"}, set()) == []


def test_superjob_missing_query_or_key_returns_empty() -> None:
    assert asyncio.run(SuperJobApiAdapter(_settings(SUPERJOB_API_QUERY="")).fetch()) == []
    assert asyncio.run(SuperJobApiAdapter(_settings(SUPERJOB_API_KEY="")).fetch()) == []
