import asyncio
from datetime import UTC, datetime

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.sources.adapters import trudvsem_vacancy_api
from tg_vacancy_bot.sources.adapters.trudvsem_vacancy_api import (
    TrudvsemApiAdapter,
    _items_to_vacancies,
)


def _api_item(
    *,
    title="Ведущий разработчик Frontend",
    url="https://trudvsem.ru/vacancy/card/1247800130082/07aed1f8",
    company="СПБ ИАЦ",
    region="Город Санкт-Петербург",
    date_modify="2026-09-16T10:00:00+0300",
    salary="от 160000",
    duty="Разрабатывать интерфейсы",
    requirements="Опыт frontend-разработки от 5 лет",
    skills=("TypeScript", "React"),
):
    return {
        "vacancy": {
            "id": "07aed1f8",
            "job-name": title,
            "vac_url": url,
            "company": {"name": company},
            "region": {"name": region},
            "creation-date": "2026-08-24",
            "date_modify": date_modify,
            "salary": salary,
            "salary_min": 160000,
            "salary_max": 200000,
            "duty": duty,
            "requirements": requirements,
            "skills": list(skills),
            "contact_list": [{"contact_type": "Телефон", "contact_value": "+7(812) 000-00-00"}],
            "contact_person": "Иванова",
        }
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
    monkeypatch.setattr(trudvsem_vacancy_api, "source_session", lambda **kwargs: session)
    return session


def _settings(**overrides):
    values = {
        "ENABLE_TRUDVSEM_API": True,
        "TRUDVSEM_API_QUERY": "frontend разработчик",
        "TRUDVSEM_API_RESULTS_WANTED": 20,
        "SOURCE_MAX_AGE_HOURS": 48,
    }
    values.update(overrides)
    return Settings(**values)


def test_trudvsem_maps_item_to_vacancy(monkeypatch) -> None:
    current = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(trudvsem_vacancy_api, "utcnow", lambda: current)
    payload = {"results": {"vacancies": [_api_item()]}}
    _install_session(monkeypatch, {"frontend разработчик": payload})

    vacancies = asyncio.run(TrudvsemApiAdapter(_settings()).fetch())

    assert len(vacancies) == 1
    vacancy = vacancies[0]
    assert vacancy.title == "Ведущий разработчик Frontend"
    assert vacancy.url == "https://trudvsem.ru/vacancy/card/1247800130082/07aed1f8"
    assert vacancy.source == "Работа России"
    assert vacancy.company == "СПБ ИАЦ"
    assert vacancy.location == "Город Санкт-Петербург"
    assert vacancy.salary == "от 160000"
    assert vacancy.published_at is not None
    assert "Разрабатывать интерфейсы" in vacancy.description
    assert "TypeScript" in vacancy.description
    # Contact details from the payload must never leak into published cards.
    assert "+7(812) 000-00-00" not in vacancy.description
    assert "+7(812) 000-00-00" not in vacancy.raw_text
    assert "Иванова" not in vacancy.description


def test_trudvsem_drops_dated_out_items(monkeypatch) -> None:
    current = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(trudvsem_vacancy_api, "utcnow", lambda: current)
    old_item = _api_item(
        title="Старый Frontend",
        url="https://trudvsem.ru/vacancy/card/1/old",
        date_modify="2026-01-01T10:00:00+0300",
    )
    fresh_item = _api_item(title="Свежий Frontend", url="https://trudvsem.ru/vacancy/card/1/new")
    _install_session(
        monkeypatch, {"frontend разработчик": {"results": {"vacancies": [old_item, fresh_item]}}}
    )

    vacancies = asyncio.run(TrudvsemApiAdapter(_settings()).fetch())

    assert [v.title for v in vacancies] == ["Свежий Frontend"]


def test_trudvsem_items_to_vacancies_ignores_malformed_payload() -> None:
    assert _items_to_vacancies(None, set()) == []
    assert _items_to_vacancies({}, set()) == []
    assert _items_to_vacancies({"results": {"vacancies": "nope"}}, set()) == []
    assert _items_to_vacancies({"results": {"vacancies": [{"vacancy": "nope"}]}}, set()) == []


def test_trudvsem_missing_query_returns_empty() -> None:
    settings = Settings(ENABLE_TRUDVSEM_API=True, TRUDVSEM_API_QUERY="")
    assert asyncio.run(TrudvsemApiAdapter(settings).fetch()) == []
