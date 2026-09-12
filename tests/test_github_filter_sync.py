from types import SimpleNamespace

import pytest

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.github_filter_sync import (
    VARIABLE_GRADES,
    VARIABLE_SPECIALTIES,
    _detect_repository_from_git,
    _run_gh,
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


def test_sync_skips_without_repository(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        "tg_vacancy_bot.github_filter_sync._detect_repository_from_git",
        lambda *args: None,
    )
    monkeypatch.setattr("tg_vacancy_bot.github_filter_sync._gh_available", lambda: True)
    monkeypatch.setattr(
        "tg_vacancy_bot.github_filter_sync._run_gh",
        lambda *args: calls.append(args) or (True, "ok"),
    )
    ok, message = sync_vacancy_filter_to_github_sync(VacancyFilter(), _settings())
    assert ok is False
    assert "no GitHub repository detected" in message
    assert calls == []


def test_sync_skips_when_no_token_and_no_gh(monkeypatch) -> None:
    settings = _settings(GITHUB_REPOSITORY="owner/repo")
    gh_calls = []
    rest_calls = []
    monkeypatch.setattr("tg_vacancy_bot.github_filter_sync._gh_available", lambda: False)
    monkeypatch.setattr(
        "tg_vacancy_bot.github_filter_sync._run_gh",
        lambda *args: gh_calls.append(args) or (True, "ok"),
    )
    monkeypatch.setattr(
        "tg_vacancy_bot.github_filter_sync._set_repository_variable",
        lambda *args: rest_calls.append(args) or (True, "ok"),
    )
    ok, message = sync_vacancy_filter_to_github_sync(VacancyFilter(), settings)
    assert ok is False
    assert "no GITHUB_FILTER_SYNC_TOKEN and no gh CLI" in message
    assert gh_calls == [] and rest_calls == []


def test_sync_uses_gh_cli_when_no_token(monkeypatch) -> None:
    settings = _settings(GITHUB_REPOSITORY="owner/repo")
    called = []
    monkeypatch.setattr("tg_vacancy_bot.github_filter_sync._gh_available", lambda: True)
    monkeypatch.setattr(
        "tg_vacancy_bot.github_filter_sync._run_gh",
        lambda owner, repo, name, value: called.append((owner, repo, name, value)) or (True, "ok"),
    )
    ok, message = sync_vacancy_filter_to_github_sync(
        VacancyFilter(specialties=("backend", "mobile"), grades=("junior", "intern")),
        settings,
    )
    assert ok is True
    assert len(called) == 2
    assert all(owner == "owner" and repo == "repo" for owner, repo, _name, _value in called)
    names = {call[2] for call in called}
    assert names == {VARIABLE_SPECIALTIES, VARIABLE_GRADES}
    values = {call[3] for call in called}
    assert values == {"backend,mobile", "junior,intern"}


def test_run_gh_clears_token_env_and_reports_success(monkeypatch) -> None:
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["env"] = kwargs["env"]
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("tg_vacancy_bot.github_filter_sync.subprocess.run", fake_run)
    ok, message = _run_gh("owner", "repo", VARIABLE_SPECIALTIES, "backend")
    assert ok is True
    assert "synced GitHub variable" in message
    assert captured["args"][:2] == ["gh", "variable"]
    assert captured["env"]["GH_TOKEN"] == ""
    assert captured["env"]["GITHUB_TOKEN"] == ""


def test_run_gh_reports_failure_without_credentials(monkeypatch) -> None:
    monkeypatch.setattr(
        "tg_vacancy_bot.github_filter_sync.subprocess.run",
        lambda args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="HTTP 401"),
    )
    ok, message = _run_gh("owner", "repo", VARIABLE_SPECIALTIES, "backend")
    assert ok is False
    assert "exit 1" in message
    assert "HTTP 401" in message
    assert "backend" not in message.split(": ")[-1]


def test_detect_repository_from_git_https(monkeypatch) -> None:
    monkeypatch.setattr(
        "tg_vacancy_bot.github_filter_sync.subprocess.run",
        lambda args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="https://github.com/BoomCoderchik/tg-vacancy-bot.git\n",
            stderr="",
        ),
    )
    assert _detect_repository_from_git() == "BoomCoderchik/tg-vacancy-bot"


def test_detect_repository_from_git_ssh(monkeypatch) -> None:
    monkeypatch.setattr(
        "tg_vacancy_bot.github_filter_sync.subprocess.run",
        lambda args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="git@github.com:BoomCoderchik/tg-vacancy-bot.git\n",
            stderr="",
        ),
    )
    assert _detect_repository_from_git() == "BoomCoderchik/tg-vacancy-bot"


def test_detect_repository_from_git_ssh_url(monkeypatch) -> None:
    monkeypatch.setattr(
        "tg_vacancy_bot.github_filter_sync.subprocess.run",
        lambda args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="ssh://git@github.com/BoomCoderchik/tg-vacancy-bot.git\n",
            stderr="",
        ),
    )
    assert _detect_repository_from_git() == "BoomCoderchik/tg-vacancy-bot"


def test_detect_repository_from_git_non_github(monkeypatch) -> None:
    monkeypatch.setattr(
        "tg_vacancy_bot.github_filter_sync.subprocess.run",
        lambda args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="https://gitlab.com/BoomCoderchik/tg-vacancy-bot.git\n",
            stderr="",
        ),
    )
    assert _detect_repository_from_git() is None


@pytest.mark.parametrize("stdout", ["", "fatal: not a git repository"])
def test_detect_repository_from_git_missing_remote(monkeypatch, stdout) -> None:
    monkeypatch.setattr(
        "tg_vacancy_bot.github_filter_sync.subprocess.run",
        lambda args, **kwargs: SimpleNamespace(returncode=128, stdout=stdout, stderr=""),
    )
    assert _detect_repository_from_git() is None


def test_sync_pushes_both_variables_via_rest(monkeypatch) -> None:
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