import pytest

from tg_vacancy_bot.app import main
from tg_vacancy_bot.config import get_settings


def test_main_reports_missing_runtime_config(capsys, monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TARGET_CHAT_ID", raising=False)
    get_settings.cache_clear()

    with pytest.raises(SystemExit) as exc:
        main(["run"])

    assert exc.value.code == 2
    assert "Missing required environment variables" in capsys.readouterr().err
    get_settings.cache_clear()
