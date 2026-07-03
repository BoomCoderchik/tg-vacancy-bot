import pytest

from tg_vacancy_bot.env_setup import init_env_file


def test_init_env_file_copies_example_without_overwriting(tmp_path) -> None:
    example = tmp_path / ".env.example"
    env = tmp_path / ".env"
    example.write_text("TELEGRAM_BOT_TOKEN=\n", encoding="utf-8")

    message = init_env_file(str(example), str(env))

    assert env.read_text(encoding="utf-8") == "TELEGRAM_BOT_TOKEN=\n"
    assert "Created" in message

    with pytest.raises(RuntimeError, match="refusing to overwrite"):
        init_env_file(str(example), str(env))
