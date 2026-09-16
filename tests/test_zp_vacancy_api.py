import asyncio
from datetime import UTC, datetime

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.sources.adapters import zp_vacancy_api
from tg_vacancy_bot.sources.adapters.zp_vacancy_api import (
    ZarplataApiAdapter,
    _items_to_vacancies,
)


def _api_item(
    *,
    title="Junior Frontend-разработчик",
    url="https://zarplata.ru/vacancy/junior-frontend?id=139080474",
    company="СКБ Контур",
    region="Екатеринбург",
    salary=None,
    published_at="2026-09-16T10:00:00+0300",
    requirement="Знание JavaScript",
    responsibility="Разработка интерфейсов",
):
    return {
        "id": 139080474,
        "name": title,
        "alternate_url": url,
        "employer": {"name": company},
        "area": {"name": region},
        "salary": salary,
        "snippet": {"requirement": requirement, "responsibility": responsibility},
        "published_at": published_at,
        "created_at": published_at,
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
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return False

        def get(self, url, params=None):
            query = (params or {}).get("text", "")
            return FakeGet(FakeResponse(data.get(query), statuses.get(query, 200)))

    return FakeSession()


def _install_session(monkeypatch, data, statuses=None):
    session = _make_session(data, statuses)
    monkeypatch.setattr(zp_vacancy_api, "source_session", lambda **kwargs: session)
    return session


def _settings(**overrides):
    values = {
        "ENABLE_ZP_API": True,
        "ZP_API_QUERY": "junior frontend",
        "ZP_API_RESULTS_WANTED": 20,
        "SOURCE_MAX_AGE_HOURS": 48,
    }
    values.update(overrides)
    return Settings(**values)


def test_zp_maps_item_to_vacancy(monkeypatch) -> None:
    current = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(zp_vacancy_api, "utcnow", lambda: current)
    payload = {"items": [_api_item(salary={"from": 60000, "to": 90000, "currency": "RUR"})]}
    _install_session(monkeypatch, {"junior frontend": payload})

    vacancies = asyncio.run(ZarplataApiAdapter(_settings()).fetch())

    assert len(vacancies) == 1
    vacancy = vacancies[0]
    assert vacancy.title == "Junior Frontend-разработчик"
    assert vacancy.url == "https://zarplata.ru/vacancy/junior-frontend?id=139080474"
    assert vacancy.source == "Зарплата.ру"
    assert vacancy.company == "СКБ Контур"
    assert vacancy.location == "Екатеринбург"
    assert vacancy.salary == "от 60000 до 90000 \u20bd"
    assert vacancy.published_at is not None
    assert "Знание JavaScript" in vacancy.description


def test_zp_drops_dated_out_items(monkeypatch) -> None:
    current = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(zp_vacancy_api, "utcnow", lambda: current)
    old_item = _api_item(
        title="Старый Frontend",
        url="https://zarplata.ru/vacancy/old?id=1",
        published_at="2026-01-01T10:00:00+03:00",
    )
    fresh_item = _api_item(title="Свежий Frontend", url="https://zarplata.ru/vacancy/new?id=2")
    _install_session(monkeypatch, {"junior frontend": {"items": [old_item, fresh_item]}})

    vacancies = asyncio.run(ZarplataApiAdapter(_settings()).fetch())

    assert [v.title for v in vacancies] == ["Свежий Frontend"]


def test_zp_error_envelope_is_skipped(monkeypatch) -> None:
    # Captcha and auth answers are never bypassed: the query just yields nothing.
    _install_session(monkeypatch, {"junior frontend": {"errors": [{"type": "forbidden"}]}})

    vacancies = asyncio.run(ZarplataApiAdapter(_settings()).fetch())

    assert vacancies == []


def test_zp_items_to_vacancies_ignores_malformed_payload() -> None:
    assert _items_to_vacancies(None, set()) == []
    assert _items_to_vacancies({}, set()) == []
    assert _items_to_vacancies({"items": "nope"}, set()) == []


def test_zp_missing_query_returns_empty() -> None:
    settings = Settings(ENABLE_ZP_API=True, ZP_API_QUERY="")
    assert asyncio.run(ZarplataApiAdapter(settings).fetch()) == []
