from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.github_filter_sync import (
    VARIABLE_GRADES,
    VARIABLE_SPECIALTIES,
    _set_repository_variable,
    sync_vacancy_filter_to_github_sync,
)
from tg_vacancy_bot.models import VacancyFilter


def _settings(**overrides) -> Settings:
    kwargs = {
        "TELEGRAM_BOT_TOKEN": "token",
        "TARGET_CHAT_ID": "@target",
        **overrides,
    }
    return Settings(**kwargs)


def test_sync_skips_when_not_configured(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        "tg_vacancy_bot.github_filter_sync._set_repository_variable",
        lambda *args: calls.append(args),
    )
    ok, message = sync_vacancy_filter_to_github_sync(VacancyFilter(), _settings())
    assert ok is False
    assert "not configured" in message
    assert calls == []


def test_sync_pushes_both_variables(monkeypatch) -> None:
    settings = _settings(
        GITHUB_FILTER_SYNC_TOKEN="secret-token",
        GITHUB_REPOSITORY="owner/repo",
    )
    called = []
    monkeypatch.setattr(
        "tg_vacancy_bot.github_filter_sync._set_repository_variable",
        lambda *args: called.append(args) or (True, "ok"),
    )
    ok, message = sync_vacancy_filter_to_github_sync(
        VacancyFilter(specialties=("backend",), grades=("junior", "intern")),
        settings,
    )
    assert ok is True
    assert "ok" in message
    assert len(called) == 2


def test_sync_pushes_exact_values_and_repository(monkeypatch) -> None:
    settings = _settings(
        GITHUB_FILTER_SYNC_TOKEN="secret-token",
        GITHUB_REPOSITORY="BoomCoderchik/tg-vacancy-bot",
    )
    calls = []
    monkeypatch.setattr(
        "tg_vacancy_bot.github_filter_sync._set_repository_variable",
        lambda *args: calls.append(args) or (True, "ok"),
    )
    ok, message = sync_vacancy_filter_to_github_sync(
        VacancyFilter(specialties=("backend", "mobile"), grades=("junior", "intern")),
        settings,
    )
    assert ok is True
    assert "ok" in message
    names = {call[3] for call in calls}
    assert names == {VARIABLE_SPECIALTIES, VARIABLE_GRADES}
    values = {call[4] for call in calls}
    assert values == {"backend,mobile", "junior,intern"}
    for owner, repo, token, _name, _value in calls:
        assert owner == "BoomCoderchik"
        assert repo == "tg-vacancy-bot"
        assert token == "secret-token"


def test_set_variable_patches_existing_variable(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        "tg_vacancy_bot.github_filter_sync._call_api",
        lambda method, url, token, payload: calls.append((method, url)) or (200, ""),
    )
    ok, message = _set_repository_variable("owner", "repo", "token", VARIABLE_SPECIALTIES, "backend")
    assert ok is True
    assert "backend" in message
    assert calls == [("PATCH", f"https://api.github.com/repos/owner/repo/actions/variables/{VARIABLE_SPECIALTIES}")]


def test_set_variable_creates_missing_variable(monkeypatch) -> None:
    calls = []
    responses = {("PATCH",): (404, ""), ("POST",): (201, "")}
    monkeypatch.setattr(
        "tg_vacancy_bot.github_filter_sync._call_api",
        lambda method, url, token, payload: calls.append((method, url)) or responses[(method,)],
    )
    ok, message = _set_repository_variable("owner", "repo", "token", VARIABLE_GRADES, "junior")
    assert ok is True
    assert "junior" in message
    assert calls[0][0] == "PATCH"
    assert calls[1][0] == "POST"
    assert calls[1][1] == "https://api.github.com/repos/owner/repo/actions/variables"


def test_failed_sync_reports_status_without_credentials(monkeypatch) -> None:
    openai_body = '{"message":"bad credentials"}'
    monkeypatch.setattr(
        "tg_vacancy_bot.github_filter_sync._call_api",
        lambda method, url, token, payload: (500, openai_body),
    )
    ok, message = _set_repository_variable("owner", "repo", "secret-token", VARIABLE_SPECIALTIES, "backend")
    assert ok is False
    assert "HTTP 500" in message
    assert "secret-token" not in message
    assert "bad credentials" not in message


def test_user_defined_repo_with_git_suffix_is_normalized(monkeypatch) -> None:
    settings = _settings(
        GITHUB_FILTER_SYNC_TOKEN="secret-token",
        GITHUB_REPOSITORY="owner/tg-vacancy-bot.git",
    )
    repos = []
    monkeypatch.setattr(
        "tg_vacancy_bot.github_filter_sync._set_repository_variable",
        lambda owner, repo, token, name, value: repos.append(repo) or (True, "ok"),
    )
    ok, _message = sync_vacancy_filter_to_github_sync(
        VacancyFilter(specialties=("backend",), grades=("junior",)),
        settings,
    )
    assert ok is True
    assert repos and all(repo == "tg-vacancy-bot" for repo in repos)