import os

import pytest

from tg_vacancy_bot import runtime_lock
from tg_vacancy_bot.runtime_lock import SingleInstanceLock, bot_run_lock_path


def test_single_instance_lock_rejects_live_existing_lock(tmp_path, monkeypatch) -> None:
    lock_path = tmp_path / "bot.lock"
    lock_path.write_text("12345\n", encoding="utf-8")
    monkeypatch.setattr(runtime_lock, "_pid_is_running", lambda pid: pid == 12345)

    with pytest.raises(RuntimeError) as exc:
        SingleInstanceLock(lock_path).acquire()

    assert "already active" in str(exc.value)
    assert "12345" in str(exc.value)


def test_single_instance_lock_replaces_stale_lock(tmp_path, monkeypatch) -> None:
    lock_path = tmp_path / "bot.lock"
    lock_path.write_text("12345\n", encoding="utf-8")
    monkeypatch.setattr(runtime_lock, "_pid_is_running", lambda pid: False)

    with SingleInstanceLock(lock_path):
        assert lock_path.read_text(encoding="utf-8") == f"{os.getpid()}\n"

    assert not lock_path.exists()


def test_bot_run_lock_path_does_not_expose_token(tmp_path) -> None:
    path = bot_run_lock_path(str(tmp_path / "vacancies.sqlite3"), "secret-token")

    assert path.parent == tmp_path
    assert "secret-token" not in path.name
    assert path.name.startswith("tg-vacancy-bot-")
